.PHONY: run dev lint format typecheck test migrate seed revision docker-up docker-down docker-logs

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn app.main:app --reload

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy app

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m app.seed

revision:
	uv run alembic revision --autogenerate -m "$(m)"

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app
