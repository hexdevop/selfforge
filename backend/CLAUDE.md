# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Backend of Self Forge (see the root `CLAUDE.md` and `../docs/` — they win over this file;
human-facing overview in `README.md`). Grown from a FastAPI starter template: users, JWT auth
by email/username (refresh token in an httpOnly cookie), email verification / password reset
over SMTP, Redis rate limiting, middlewares, generic repository with filters, pagination,
Redis caching. On top of it: the reference catalog, profile and places, the program engine,
workouts, progress analytics, body metrics with photos in S3, the weather forecast and a
full data export.

## Commands

```bash
uv sync                              # install deps (dev group included by default)

make dev                             # uvicorn --reload
make lint                            # ruff check + ruff format --check
make format                          # ruff check --fix + ruff format
make typecheck                       # mypy app (strict)
make test                            # pytest
uv run pytest tests/test_auth.py -k test_login_by_email_or_username   # single test

make migrate                         # alembic upgrade head
make seed                            # upsert the reference catalog from seed/*.yaml
make revision m="add something"      # alembic revision --autogenerate

make docker-up / make docker-down    # full stack (app + postgres + redis) via docker-compose
```

`pnpm` isn't on PATH on the dev machine: the frontend runs as `corepack pnpm …`.

Tests run against a real Postgres (the models rely on JSONB) + `fakeredis`. Start the DB
with `docker compose up -d db` first (`docker compose up -d db redis minio mailpit` for
running the app); `tests/conftest.py` creates the `app_test` database on
first run, builds the schema via `Base.metadata.create_all` once per session and truncates
all tables after every test. The app's own `get_db` is used as-is — no override.

## Environment

Config is `app/core/config.py` (`pydantic-settings`), reading `.env`. Copy `.env.example` to
`.env` to get started; `.env.test` is used automatically by pytest (see
`pyproject.toml`'s `[tool.pytest.ini_options].env_files`).

`DATABASE_URL`/`REDIS_URL` are always *derived* from individual `POSTGRES_*`/`REDIS_*` fields,
never set directly — this is what lets `docker-compose.yml` override just `POSTGRES_HOST`/
`REDIS_HOST` (to `db`/`redis`) for the containerized app while `.env` keeps `localhost` for
non-Docker local runs. The Postgres/Redis containers publish on non-default host ports
(`POSTGRES_EXPOSED_PORT=5433`, `REDIS_EXPOSED_PORT=6380`) specifically to avoid clashing with
services already running natively on a dev machine — the app itself never uses these two vars.

## Architecture

Request flow is strictly layered: `api/v1/*` (HTTP/validation only) → `services/*` (business
rules, transaction boundaries, cache invalidation) → `repositories/*` (query building) →
`models/*` (SQLAlchemy ORM). Routes never touch the DB session or ORM models directly — they
call a service and return a `schemas/*` Pydantic model. Services own `session.commit()`;
repositories only `flush()`.

- **`app/repositories/base.py`** — generic `BaseRepository[ModelType: Base]` (PEP 695 generic)
  with `get`/`get_by`/`list`/`create`/`update`/`delete`. `list()` takes a plain dict of
  Django-style filters (`app/repositories/filters.py`, e.g. `{"email__ilike": "%x%"}`,
  `{"created_at__gte": ...}`) and a `PageParams`, returning a `Page[ModelType]`
  (`app/schemas/pagination.py`). New repositories (`app/repositories/user.py` is the example)
  just subclass and add the queries that don't fit the generic shape.

- **Auth** (`app/services/auth.py`, `app/core/security.py`) — access tokens are short-lived
  stateless JWTs; refresh tokens are random strings whose *hash* is persisted in
  `app/models/refresh_token.py` (the raw value is never stored), so sessions can be revoked
  server-side. Every `/auth/refresh` call rotates the token: the old one is revoked and a new
  pair issued. `login` accepts either email or username via `UserRepository.get_by_login`.

- **Caching** (`app/cache/decorator.py`) — `@cached(key_prefix=...)` wraps an async method and
  caches its *JSON-serializable* return value in Redis; the key is built from primitive
  positional/keyword args only (a bound `self` or a DB session is silently skipped). It is only
  ever applied to methods returning plain dicts (e.g. `UserService.get_cached`, which returns
  `UserRead.model_dump(mode="json")`), never raw ORM objects. Pair every write path that
  invalidates cached data with `invalidate_prefix(prefix)` (see `UserService.update`/`delete`).

- **Exceptions** (`app/core/exceptions.py`) — business/domain errors raise `AppException`
  subclasses (`NotFoundException`, `AlreadyExistsException`, etc.), never `HTTPException`,
  from services/repositories. Handlers in `app/main.py` convert them (and validation /
  HTTP errors) to `{"detail": {"code", "message", "fields"}}` (`app/schemas/error.py`) —
  `message` is Russian and shown to the user; `fields` maps form fields to messages.

- **Alembic** (`alembic/env.py`) ignores `alembic.ini`'s `sqlalchemy.url` and instead builds the
  URL from `app.core.config.settings` at runtime, and imports `app.models` (which re-exports
  every model) so `target_metadata = Base.metadata` sees the full schema for autogenerate.
  `alembic/versions/` is excluded from ruff/mypy — it's generated code, left as Alembic writes it.

- **`Page[T]`** (`app/schemas/pagination.py`) sets `arbitrary_types_allowed=True` deliberately:
  repositories return `Page[SomeORMModel]` internally, which routes then re-validate into
  `Page[SomeReadSchema]` before returning — see `list_users` in `app/api/v1/users.py` for the
  pattern.

- **Catalog** (`app/models/catalog.py`, `seed/`) — patterns, equipment, exercises and skills
  are reference data: never in migrations, only in `seed/*.yaml`, loaded by `app/seed.py`.
  `load_catalog()` cross-validates everything (ladder links stay within a pattern and go the
  right way, equipment codes exist, skills point to real exercises, timed exercises have no
  `bodyweight_share`, a skill's `goal` uses the same unit as its exercise) before upserting by
  `code`/`slug`. The seed then drops the `catalog:*` Redis prefix; catalog endpoints add an
  ETag and answer `If-None-Match` with 304.

- **Engine** (`app/engine/`) — the product core: inventory and weight grids, level
  assessment, ladders, goal schemes, progression levers, the mesocycle and one-off days,
  preparing/substituting/trimming/moving a session, analytics, the weather verdict. Pure:
  dataclasses in, dataclasses out; no SQLAlchemy, FastAPI, Redis, httpx or boto3 —
  `tests/engine/test_purity.py` enforces it. Services build engine inputs from models
  (`to_engine_location`, `CatalogService.engine_exercises`, `logged_set`) and persist results.
  Russian texts shown to people (`hint_ru`, `notes_ru`, `rationale_ru`, `text_ru`) are
  produced by the engine next to the decision they explain. Spec: `../docs/03-engine.md`.

- **Workouts** (`app/services/workout.py`) — a session stores the engine's prepared plan in
  `workout_sessions.plan` (JSONB) and rebuilds the engine `Session` from it for substitute /
  trim / swap-location. Progression history is keyed by the plan slot (`planned_slug`), not
  by exercise. Sets are idempotent on `client_uuid` (`INSERT … ON CONFLICT DO NOTHING`).

- **Storage** (`app/storage.py`) — S3/MinIO via boto3. The API reaches storage at
  `S3_ENDPOINT_URL` but signs browser links for `S3_PUBLIC_URL` (the signature binds the
  host). Uploads are presigned POST so the policy caps size and type. Network calls
  (`ensure_bucket`, `delete`) run in a thread; tests monkeypatch them.

- **Weather** (`app/weather.py`) — Open-Meteo over httpx, cached in Redis per rounded
  coordinates and hour; failures raise `ServiceUnavailableException` (503). Tests
  monkeypatch `app.weather._fetch`.

- **Production** — `../deploy/` (compose behind the host nginx, deploy/backup/restore
  scripts) and `../docs/07-deploy.md`. uvicorn runs with `--proxy-headers` there so rate
  limiting sees client IPs.

## Adding a new domain (e.g. "posts")

Mirror the `user` slice: `models/post.py` → add to `models/__init__.py` → `schemas/post.py` →
`repositories/post.py` (subclass `BaseRepository[Post]`) → `services/post.py` → `api/v1/posts.py`
→ register in `api/v1/router.py` → `make revision m="add posts"` → `make migrate`.
