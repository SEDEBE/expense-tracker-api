.PHONY: install dev db test lint format messages compilemessages up down migrate superuser worker beat

install:  ## Install all dependencies (including dev) into .venv
	uv sync
	uv run pre-commit install

dev: compilemessages ## Run the API locally with autoreload (needs `make db`)
	uv run python manage.py migrate
	uv run python manage.py runserver

worker: ## Run a Celery worker locally (needs `make db`)
	uv run celery -A config worker --loglevel info

beat: ## Run Celery beat locally (needs `make db`)
	uv run celery -A config beat --loglevel info

db:  ## Start Postgres, Redis and Mailplit in Docker
	docker compose up -d db redis mailpit

test: compilemessages ## Run the test suite with coverage
	uv run pytest --cov --cov-report=term-missing

lint:  ## Check style and common bugs
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-fix style
	uv run ruff check --fix .
	uv run ruff format .

messages:  ## Extract translatable strings into locale/es/LC_MESSAGES/django.po
	uv run python manage.py makemessages -l es

compilemessages:  ## Compile .po translations into the .mo files Django reads
	uv run python manage.py compilemessages --ignore=.venv

up:  ## Build and start the whole stack (API, worker, beat, Postgres, Redis, Mailpit)
	docker compose up --build -d

down:  ## Stop the stack
	docker compose down

superuser:
	uv run python manage.py createsuperuser
