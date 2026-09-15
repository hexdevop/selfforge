# Self Forge — бэкенд

API приложения Self Forge. Вырос из шаблона fastapi-template: пользователи,
JWT-аутентификация по email/username, миддлвари, generic-репозитории с фильтрами
и пагинацией, кеширование в Redis. Продуктовые спецификации — в `../docs/`.

## Стек

- **FastAPI** + **Pydantic v2** (`pydantic-settings` для конфига)
- **SQLAlchemy 2.0** (async) + **PostgreSQL** (`asyncpg`) + **Alembic**
- **Redis** — кеш
- **JWT** (access + refresh с ротацией и хранением refresh-токенов в БД)
- **uv** — управление зависимостями и окружением
- **ruff** + **mypy** (strict) — линт, форматирование, типы
- **pytest** + **pytest-asyncio** — тесты на PostgreSQL + fakeredis

## Архитектура

```
app/
├── core/            # конфиг, security (JWT/хеши паролей), исключения, логирование
├── db/              # engine/session, декларативная база + миксины (UUID pk, timestamps)
├── models/          # SQLAlchemy-модели
├── schemas/         # Pydantic-схемы (request/response), пагинация
├── repositories/    # generic CRUD-репозиторий + dict-фильтры (Django-style lookups)
├── services/        # бизнес-логика (auth, users), в т.ч. пример кеширования
├── cache/           # Redis-клиент + декоратор @cached / invalidate_prefix
├── middlewares/      # request-id, access-логирование
├── dependencies/     # get_current_user и т.п., DI-обёртки
├── api/v1/           # роутеры, версионирование через префикс /api/v1
└── main.py           # сборка приложения (lifespan, middlewares, exception handlers)
alembic/               # миграции
tests/                 # pytest, отдельная БД app_test в Postgres и fakeredis
```

Поток вызова: `api/v1/*` → `services/*` (бизнес-правила, транзакции) →
`repositories/*` (доступ к БД) → `models/*`. Ответы всегда сериализуются через
`schemas/*`, наружу ORM-объекты не отдаются напрямую.

### Слой фильтров и пагинации

`BaseRepository.list(filters, pagination, order_by)` принимает Django-style
словарь фильтров: `{"is_active": True, "email__ilike": "%gmail%"}`. Поддерживаемые
операторы — `eq/ne/gt/gte/lt/lte/in/not_in/like/ilike/is_null` (см.
`app/repositories/filters.py`). Пагинация — `PageParams(page, size)`, ответ —
`Page[T]` с `total`/`pages`.

### Аутентификация

`POST /api/v1/auth/register|login|refresh|logout`, `GET /api/v1/auth/me`.
Логин принимает `login` — email **или** username. Access-токен — короткоживущий
stateless JWT. Refresh-токен — случайная строка, в БД хранится только её хеш
(`app/models/refresh_token.py`), что позволяет отзывать сессии; при каждом
`/refresh` токен ротируется (старый отзывается, выдаётся новый).

### Кеширование

`app/cache/decorator.py` — декоратор `@cached(key_prefix=...)` кеширует
JSON-сериализуемый результат async-функции в Redis, автоматически строя ключ
из примитивных аргументов (пропуская `self`/сессию БД). Пример использования —
`UserService.get_cached`, с инвалидацией через `invalidate_prefix(...)` в
`update`/`delete`.

## Быстрый старт

### Вариант 1 — Docker (рекомендуется)

```bash
cp .env.example .env      # при необходимости поправить SECRET_KEY и т.д.
docker compose up --build
uv run alembic upgrade head   # применить миграции (или через `make migrate` из контейнера)
```

API будет доступен на `http://localhost:8000`, документация — на `/docs`.
Postgres и Redis внутри docker-сети видны приложению как `db`/`redis` — эти
хосты подставляются автоматически через `environment:` в `docker-compose.yml`,
поверх значений из `.env`. Наружу они пробрасываются на **нестандартные**
порты (`POSTGRES_EXPOSED_PORT=5433`, `REDIS_EXPOSED_PORT=6380`), чтобы не
конфликтовать с локально установленными Postgres/Redis.

### Вариант 2 — приложение на хосте, сервисы в Docker

`.env.example` уже смотрит на порты контейнеров (5433 / 6380 / 1025).

```bash
cp .env.example .env
docker compose up -d db redis mailpit minio
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Письма в dev ловит Mailpit: http://localhost:8025. Консоль MinIO: http://localhost:9001.

## Команды

| Команда | Что делает |
|---|---|
| `make dev` | запуск с автоперезагрузкой |
| `make lint` | `ruff check` + `ruff format --check` |
| `make format` | автоформатирование |
| `make typecheck` | `mypy` (strict) |
| `make test` | `pytest` |
| `make migrate` | `alembic upgrade head` |
| `make revision m="сообщение"` | новая миграция (autogenerate) |
| `make docker-up` / `make docker-down` | поднять/остановить весь стек в Docker |

## Тесты

Тесты идут на настоящем PostgreSQL (модель данных опирается на JSONB), кеш —
`fakeredis`. База `app_test` создаётся автоматически при первом запуске.

```bash
docker compose up -d db
uv run pytest
```

## CI

`../.github/workflows/ci.yml` (в корне монорепозитория): для бэкенда — `ruff check`,
`ruff format --check`, `mypy`, `pytest` на Postgres-сервисе; для фронта — lint, typecheck,
test, build и проверка, что `src/api/schema.d.ts` совпадает со схемой бэкенда.
