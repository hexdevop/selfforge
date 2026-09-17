# Self Forge — бэкенд

API приложения Self Forge на FastAPI. Общий обзор проекта — [корневой README](../README.md),
продуктовые спецификации — [`../docs/`](../docs/).

## Оглавление

- [Стек](#стек)
- [Архитектура](#архитектура)
  - [Слои](#слои)
  - [Движок](#движок)
  - [Внешние зависимости](#внешние-зависимости)
  - [Фильтры и пагинация](#фильтры-и-пагинация)
  - [Аутентификация](#аутентификация)
  - [Кеширование](#кеширование)
- [Быстрый старт](#быстрый-старт)
- [Настройки](#настройки)
- [Команды](#команды)
- [Миграции и справочник](#миграции-и-справочник)
- [Тесты](#тесты)
- [CI и прод](#ci-и-прод)

## Стек

- **FastAPI** + **Pydantic v2** (`pydantic-settings` для конфига)
- **SQLAlchemy 2.0** (async) + **PostgreSQL 16** (`asyncpg`) + **Alembic**
- **Redis** — кеш справочника и прогноза, rate limiting
- **JWT**: access в памяти клиента, refresh с ротацией в httpOnly-cookie, хеш — в БД
- **S3 (MinIO)** через `boto3` — фото прогресса по presigned-ссылкам
- **httpx** — прогноз погоды (Open-Meteo)
- **uv**, **ruff**, **mypy** (strict), **pytest** + **pytest-asyncio** + **fakeredis**

## Архитектура

```
app/
├── api/v1/          роутеры: auth, catalog, profile, locations, programs, sessions,
│                    progress, body, weather, export; /health — отдельно
├── services/        бизнес-правила, границы транзакций, сборка входа для движка
├── repositories/    запросы к БД: generic CRUD + специфичные выборки
├── models/          SQLAlchemy-модели
├── schemas/         Pydantic-схемы запросов и ответов
├── engine/          движок — чистая логика без БД и HTTP (см. ниже)
├── storage.py       объектное хранилище: presigned-формы загрузки и ссылки на просмотр
├── weather.py       клиент прогноза с кешем в Redis
├── seed.py          загрузка справочника из seed/*.yaml с перекрёстной проверкой
├── core/            конфиг, security, исключения, письма
├── cache/           Redis-клиент, @cached / invalidate_prefix
├── dependencies/    текущий пользователь, БД, пагинация, rate limit
├── middlewares/     request-id, access-логи
├── db/              engine/session, декларативная база, миксины (UUID pk, timestamps)
└── main.py          сборка приложения
alembic/             миграции
seed/                справочник: паттерны, оборудование, упражнения, навыки
tests/               API-тесты; tests/engine/ — табличные тесты движка
```

### Слои

`api/v1/*` → `services/*` → `repositories/*` → `models/*`. Роутеры только принимают запрос и
отдают схему; сервисы владеют `commit()`, репозитории — только `flush()`. ORM-объекты наружу
не отдаются. Доменные ошибки — подклассы `AppException` (`app/core/exceptions.py`), которые
превращаются в `{"detail": {"code", "message", "fields"}}` с русским `message`.

### Движок

`app/engine/` не импортирует SQLAlchemy, FastAPI, Redis, boto3, httpx — это проверяет
`tests/engine/test_purity.py`. Сервисы собирают для него входные dataclass-структуры из
моделей и сохраняют результат. Что где: инвентарь и сетка весов, оценка уровня, лестницы,
цели, рычаги прогрессии, мезоцикл, подготовка и перестройка тренировки, аналитика, погода —
подробно в [docs/03-engine.md](../docs/03-engine.md).

### Внешние зависимости

- **Хранилище** (`app/storage.py`). API ходит в S3 по `S3_ENDPOINT_URL`, а ссылки для браузера
  подписывает на `S3_PUBLIC_URL` — подпись привязана к хосту. Загрузка — presigned POST:
  его политика ограничивает размер и тип файла. Бакет создаётся при первой загрузке.
- **Прогноз** (`app/weather.py`). Open-Meteo без ключа; ответ кешируется в Redis по
  координатам, округлённым до ~1 км, и часу. Недоступность провайдера — 503 с понятным
  текстом.

### Фильтры и пагинация

`BaseRepository.list(filters, pagination, order_by)` принимает Django-style словарь:
`{"is_active": True, "email__ilike": "%gmail%"}`. Операторы —
`eq/ne/gt/gte/lt/lte/in/not_in/like/ilike/is_null` (`app/repositories/filters.py`).
Пагинация — `PageParams(page, size)`, ответ — `Page[T]`.

### Аутентификация

`login` принимает email **или** username. Access-токен — короткоживущий JWT. Refresh-токен —
случайная строка, в БД только её хеш (`app/models/refresh_token.py`); при каждом `/refresh`
ротируется. Подтверждение адреса и сброс пароля — по ссылкам из писем. `login` и
`register` ограничены по частоте на IP через Redis.

### Кеширование

`@cached(key_prefix=...)` (`app/cache/decorator.py`) кеширует JSON-результат async-метода в
Redis. Справочник кешируется и отдаётся с `ETag`; `make seed` сбрасывает его кеш.

## Быстрый старт

Приложение на хосте, сервисы в Docker (`.env.example` уже смотрит на их порты):

```bash
cp .env.example .env
docker compose up -d db redis minio mailpit
uv sync
make migrate
make seed
make dev                  # http://localhost:8000, Swagger — /docs
```

- Mailpit (письма): http://localhost:8025
- Консоль MinIO: http://localhost:9001 (`minioadmin` / `minioadmin`)

Порты Postgres и Redis наружу — нестандартные (5433 и 6380), чтобы не мешать локально
установленным. Весь стек целиком в Docker: `make docker-up` (миграции и `make seed` —
отдельно).

## Настройки

Все — в `app/core/config.py`, значения — из `.env` (образец — [`.env.example`](.env.example)).
Основные группы: `SECRET_KEY` и сроки токенов; `POSTGRES_*`, `REDIS_*`; `FRONTEND_URL` для
ссылок в письмах; `SMTP_*` и `EMAIL_FROM`; `S3_*` для фото; `WEATHER_API_URL`.
`DATABASE_URL` и `REDIS_URL` не задаются — собираются из отдельных полей. В `staging` и
`production` приложение не стартует со слабым `SECRET_KEY`.

## Команды

| Команда | Что делает |
|---|---|
| `make dev` | запуск с автоперезагрузкой |
| `make lint` | `ruff check` + `ruff format --check` |
| `make format` | автоисправление и форматирование |
| `make typecheck` | `mypy` strict |
| `make test` | `pytest` |
| `make migrate` | `alembic upgrade head` |
| `make revision m="…"` | новая миграция (autogenerate) |
| `make seed` | залить справочник из `seed/*.yaml` (идемпотентно) |
| `make docker-up` / `make docker-down` | весь стек в Docker |

Один тест: `uv run pytest tests/test_sessions.py -k resume`.

## Миграции и справочник

- Любое изменение модели — с миграцией: `make revision m="add something"`, проверить
  сгенерированный файл, `make migrate`.
- Справочные данные в миграции не кладутся. Упражнения, паттерны, оборудование и навыки —
  в `seed/*.yaml`; `make seed` проверяет всё вместе (ссылки лестниц, коды оборудования,
  цели навыков в тех же единицах, что упражнение) и делает upsert по `slug`/`code`.
  Строки, убранные из YAML, в базе остаются: история ссылается на упражнения по slug.

## Тесты

Настоящий PostgreSQL (модель данных опирается на JSONB) + `fakeredis`. Внешние сервисы в
тестах подменяются: прогноз — фейковым ответом, хранилище — без сетевых вызовов (presigned
подписи считаются по-настоящему, локально).

```bash
docker compose up -d db
make test
```

База `app_test` создаётся сама, схема строится один раз на прогон, таблицы очищаются после
каждого теста. Настройки тестов — `.env.test`, подхватывается автоматически.

## CI и прод

- CI — [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml): `ruff check`,
  `ruff format --check`, `mypy`, `pytest` на сервисе Postgres; для фронта — проверка, что
  типы API совпадают со схемой бэкенда.
- Прод-образ — [`Dockerfile`](Dockerfile); прод-стек, nginx и бэкапы —
  [`../deploy/`](../deploy/) и [docs/07-deploy.md](../docs/07-deploy.md).
