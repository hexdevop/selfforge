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

## Каталог проекта на сервере

Проект можно положить в **любую папку** — скрипты сами переходят в `deploy/` рядом с собой,
а compose ссылается на `../backend` и `../frontend` относительными путями. Ниже путь везде
задан переменной `APP_DIR`; подставь свой один раз в начале сессии:

```bash
APP_DIR=/home/deploy/apps/selfforge     # твоя папка
```

Имя папки на запуск не влияет: имя проекта Docker Compose зафиксировано в
`deploy/docker-compose.yml` (`name: selfforge`), поэтому контейнеры и тома называются
одинаково где бы ни лежал код. Переносить проект в другую папку можно — данные живут в
томах Docker, а не в каталоге проекта.

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
mkdir -p "$(dirname "$APP_DIR")"
git clone <адрес репозитория> "$APP_DIR"
cd "$APP_DIR"
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
```

Если папка вне домашнего каталога (например, в `/opt`), сначала создать её с правами
пользователя, от которого будет запускаться деплой:
`sudo mkdir -p "$APP_DIR" && sudo chown "$USER" "$APP_DIR"`. Пользователь должен
состоять в группе `docker`.

В `deploy/.env` заполнить: `SECRET_KEY`, `POSTGRES_PASSWORD`, `S3_SECRET_KEY` — каждый через
`openssl rand -hex 32`; SMTP любого почтового провайдера (без него не придут письма
подтверждения адреса и сброса пароля). Если порты 8011–8013 на сервере заняты — поменять
их и в `.env`, и в `upstream` в конфиге nginx.

**4. Приложение.**

```bash
"$APP_DIR/deploy/deploy.sh"
```

Скрипт соберёт образы, поднимет хранилища, применит миграции, загрузит справочник
упражнений и закончит проверкой `/health` и главной страницы через опубликованные порты.

**5. Сертификат и nginx.** Сначала сертификат, и только потом конфиг сайта: он ссылается на
файлы сертификата, и пока их нет, `nginx -t` падает — а вместе с ним и сам certbot, который
перед выпуском проверяет конфиг. Поэтому, если сайт уже подключён (например, после неудачной
попытки), сначала убрать ссылку: `sudo rm -f /etc/nginx/sites-enabled/selfforge.hexdevop.ru.conf`.

```bash
sudo certbot certonly --nginx -d selfforge.hexdevop.ru
sudo cp "$APP_DIR/deploy/nginx/selfforge.hexdevop.ru.conf" /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/selfforge.hexdevop.ru.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Плагин `--nginx` создаёт `options-ssl-nginx.conf` и `ssl-dhparams.pem`, на которые ссылается
конфиг. Если nginx на сервере подключает сайты не через `sites-enabled`, а через `conf.d/`, —
скопировать файл туда. Если сертификаты на сервере выпускаются иначе — поправить пути в двух строках
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
cd "$APP_DIR"
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
sudo touch /var/log/selfforge-backup.log && sudo chown "$USER" /var/log/selfforge-backup.log
crontab -e
```

В crontab переменные из shell не подставляются — путь к проекту пишется полностью:

```
30 3 * * * /home/deploy/apps/selfforge/deploy/backup.sh >> /var/log/selfforge-backup.log 2>&1
```

Проверить без ожидания ночи: `"$APP_DIR/deploy/backup.sh"` — в конце выведет размер дампа
и зеркала фото.

Бэкапы на том же диске не переживут потерю сервера. Если появится второе место — хватит
раз в сутки копировать туда `/var/backups/selfforge` (`rsync`, `rclone`).

## Восстановление

```bash
"$APP_DIR/deploy/restore.sh" /var/backups/selfforge/db/daily/selfforge_2026-09-17_0330.dump
# и фото из зеркала — добавить --photos в конце
```

Скрипт спросит подтверждение, остановит API на время восстановления и поднимет его обратно.

## Полезные команды

```bash
cd "$APP_DIR/deploy"
docker compose ps                       # состояние сервисов
docker compose logs -f api              # логи API (web, minio, db — так же)
docker compose restart api              # перезапуск одного сервиса
docker compose exec db psql -U selfforge selfforge   # консоль базы
```

Остановить всё, **сохранив** данные: `docker compose down`. Флаг `-v` у этой команды удаляет
тома — базу и фото — без возможности вернуть.

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
