# Деплой

Один VPS, на котором уже работает nginx. Приложение поднимается через Docker Compose
из `deploy/` и слушает только `127.0.0.1`; наружу его отдаёт хостовый nginx по HTTPS.

```
Интернет ──443──▶ nginx на хосте (TLS, selfforge.hexdevop.ru)
                   ├─ /                 → 127.0.0.1:8011  web    (статика фронта)
                   ├─ /api/, /health    → 127.0.0.1:8012  api    (FastAPI, 2 воркера)
                   └─ /progress-photos  → 127.0.0.1:8013  minio  (фото по подписанным ссылкам)
                  внутри compose: db (PostgreSQL 16), redis — наружу не опубликованы
```

Фото идут через тот же поддомен: ссылки подписаны на `https://selfforge.hexdevop.ru`, nginx
передаёт путь и `Host` без изменений, иначе MinIO отклонит подпись. Отдельная DNS-запись для
хранилища не нужна.

## Что лежит в репозитории

| Файл | Зачем |
|---|---|
| `deploy/docker-compose.yml` | прод-стек: db, redis, minio, api, web |
| `deploy/.env.example` | все настройки; на сервере копируется в `deploy/.env` (в git не попадает) |
| `deploy/nginx/selfforge.hexdevop.ru.conf` | сайт для хостового nginx |
| `deploy/deploy.sh` | сборка, миграции, справочник упражнений, запуск, проверка |
| `deploy/backup.sh` | ночной бэкап базы и фото на диск сервера |
| `deploy/restore.sh` | восстановление базы (и при желании фото) из бэкапа |
| `frontend/Dockerfile`, `frontend/nginx.conf` | образ фронта |

## Первый запуск

**1. DNS.** A-запись `selfforge.hexdevop.ru` → IP сервера (и AAAA, если есть IPv6).

**2. Docker.** На сервере нужны Docker Engine и плагин Compose v2 (`docker compose version`).

**3. Код и настройки.**

```bash
sudo mkdir -p /srv/selfforge && sudo chown "$USER" /srv/selfforge
git clone <адрес репозитория> /srv/selfforge
cd /srv/selfforge
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
```

В `deploy/.env` заполнить: `SECRET_KEY`, `POSTGRES_PASSWORD`, `S3_SECRET_KEY` — каждый через
`openssl rand -hex 32`; SMTP любого почтового провайдера (без него не придут письма
подтверждения адреса и сброса пароля). Если порты 8011–8013 на сервере заняты — поменять
их и в `.env`, и в `upstream` в конфиге nginx.

**4. Приложение.**

```bash
./deploy/deploy.sh
```

Скрипт соберёт образы, поднимет хранилища, применит миграции, загрузит справочник
упражнений и закончит проверкой `/health` и главной страницы через опубликованные порты.

**5. Сертификат и nginx.** Сначала сертификат — конфиг сайта ссылается на его файлы:

```bash
sudo certbot certonly --nginx -d selfforge.hexdevop.ru
sudo cp deploy/nginx/selfforge.hexdevop.ru.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/selfforge.hexdevop.ru.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Плагин `--nginx` создаёт `options-ssl-nginx.conf` и `ssl-dhparams.pem`, на которые ссылается
конфиг. Если сертификаты на сервере выпускаются иначе — поправить пути в двух строках
`ssl_certificate*` и убрать `include`/`ssl_dhparam`, если этих файлов нет. Продление certbot
делает сам.

**6. Проверка.**

```bash
curl -fsS https://selfforge.hexdevop.ru/health
```

Открыть сайт с телефона, зарегистрироваться, загрузить фото на экране «Тело и замеры»,
на iPhone — установить через Safari → «Поделиться» → «На экран „Домой“».

## Обновление

```bash
cd /srv/selfforge
git pull
./deploy/deploy.sh
```

Миграции и справочник применяются при каждом запуске скрипта — оба шага идемпотентны.
Пользователи с открытым приложением увидят «Есть новая версия» и обновятся по тапу.

## Бэкапы

Хранятся на диске сервера в `BACKUP_DIR` (по умолчанию `/var/backups/selfforge`):

- `db/daily/` — сжатый `pg_dump` за последние 7 ночей, `db/weekly/` — 4 воскресных;
  каждый дамп проверяется `pg_restore --list` перед тем, как считаться бэкапом;
- `photos/` — зеркало бакета с фото. Удалённое человеком фото пропадает и из зеркала:
  удаление приватного фото должно означать, что его нет.

Cron — раз в сутки ночью:

```bash
sudo mkdir -p /var/backups/selfforge && sudo chown "$USER" /var/backups/selfforge
crontab -e
# 30 3 * * * /srv/selfforge/deploy/backup.sh >> /var/log/selfforge-backup.log 2>&1
```

Бэкапы на том же диске не переживут потерю сервера. Если появится второе место — хватит
раз в сутки копировать туда `/var/backups/selfforge` (`rsync`, `rclone`).

## Восстановление

```bash
./deploy/restore.sh /var/backups/selfforge/db/daily/selfforge_2026-09-17_0330.dump
# и фото из зеркала — добавить --photos
```

Скрипт спросит подтверждение, остановит API на время восстановления и поднимет его обратно.

## Заметки

- **MinIO.** Community-образы больше не публикуются в Docker Hub; стек берёт
  `quay.io/minio/minio`, закреплённый по дайджесту (RELEASE.2025-09-07), — сборка
  воспроизводима, но обновлений безопасности у этой ветки не будет. Когда понадобится
  замена, её достаточно сделать S3-совместимой: приложение говорит с хранилищем только по S3.
- **Прогноз погоды.** Open-Meteo бесплатен для некоммерческого использования; для
  коммерческого нужен платный план. Адрес задаётся `WEATHER_API_URL`.
- **IP клиентов.** API ограничивает попытки входа по IP. nginx передаёт реальный адрес в
  `X-Forwarded-For`, uvicorn запущен с `--proxy-headers` — доверять заголовку безопасно,
  потому что порт API доступен только с самого сервера.
- **Другое окружение.** Все скрипты и compose понимают `SELFFORGE_ENV_FILE=/путь/к/env` —
  например, для staging-копии рядом с продом.
