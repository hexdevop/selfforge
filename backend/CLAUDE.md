# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A lightweight, reusable FastAPI starter template (not a specific product) — meant to be
copied/forked as the base for future small-to-medium projects. It ships ready-made building
blocks (users, JWT auth by email/username, middlewares, generic repository with filters,
pagination, Redis caching) that a new project can extend rather than rebuild.

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
make revision m="add something"      # alembic revision --autogenerate

make docker-up / make docker-down    # full stack (app + postgres + redis) via docker-compose
```

Tests run against SQLite in-memory (`aiosqlite`) + `fakeredis` — no Docker/Postgres/Redis
needed for `make test`. Real Postgres/Redis are only needed for `make migrate` /
`make docker-up` / running the app itself.

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
  from services/repositories. A single handler in `app/main.py` converts them to
  `{"error_code", "detail"}` JSON responses — this keeps HTTP status codes out of the service
  layer.

- **Alembic** (`alembic/env.py`) ignores `alembic.ini`'s `sqlalchemy.url` and instead builds the
  URL from `app.core.config.settings` at runtime, and imports `app.models` (which re-exports
  every model) so `target_metadata = Base.metadata` sees the full schema for autogenerate.
  `alembic/versions/` is excluded from ruff/mypy — it's generated code, left as Alembic writes it.

- **`Page[T]`** (`app/schemas/pagination.py`) sets `arbitrary_types_allowed=True` deliberately:
  repositories return `Page[SomeORMModel]` internally, which routes then re-validate into
  `Page[SomeReadSchema]` before returning — see `list_users` in `app/api/v1/users.py` for the
  pattern.

## Adding a new domain (e.g. "posts")

Mirror the `user` slice: `models/post.py` → add to `models/__init__.py` → `schemas/post.py` →
`repositories/post.py` (subclass `BaseRepository[Post]`) → `services/post.py` → `api/v1/posts.py`
→ register in `api/v1/router.py` → `make revision m="add posts"` → `make migrate`.
