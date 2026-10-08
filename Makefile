.PHONY: install dev db test lint format up down migrate superuser

install:  ## Install all dependencies (including dev) into .venv
	uv sync

dev:  ## Run the API locally with autoreload (needs `make db`)
	uv run python manage.py migrate
	uv run python manage.py runserver

db:  ## Start only Postgres in Docker
	docker compose up -d db

test:  ## Run the test suite with coverage
	uv run pytest --cov --cov-report=term-missing

lint:  ## Check style and common bugs
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-fix style
	uv run ruff check --fix .
	uv run ruff format .

up:  ## Build and start the whole stack (API + Postgres)
	docker compose up --build -d

down:  ## Stop the stack
	docker compose down

superuser:
	uv run python manage.py createsuperuser
