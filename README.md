# Expense Tracker API

[![CI](https://github.com/SEDEBE/expense-tracker-api/actions/workflows/ci.yml/badge.svg)](https://github.com/SEDEBE/expense-tracker-api/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.14-blue)
![Django](https://img.shields.io/badge/django-5.2_LTS-green)

REST API to track personal expenses: register, log in with JWT, record expenses by category
and get monthly summaries.

> 🚧 Work in progress. Done so far: project setup, users and JWT auth, categories. Next: expenses.

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.14, Django 5.2 LTS, Django REST Framework |
| Auth | JWT (`djangorestframework-simplejwt`), email-based custom user |
| Database | PostgreSQL 18 |
| API docs | OpenAPI 3 with `drf-spectacular` (Swagger UI) |
| Quality | pytest + pytest-django, factory_boy, coverage, Ruff |
| DevOps | Docker (multi-stage, non-root), Docker Compose, GitHub Actions, Dependabot |
| Tooling | [uv](https://docs.astral.sh/uv/) for dependencies and virtualenv |

## Quick start (Docker)

Only Docker is required.

```bash
git clone https://github.com/SEDEBE/expense-tracker-api.git
cd expense-tracker-api
cp .env.example .env
docker compose up --build
```

- API docs (Swagger UI): http://localhost:8000/api/docs/
- Health check: http://localhost:8000/api/health/
- Admin: http://localhost:8000/admin/ (create a user with `docker compose exec api python manage.py createsuperuser`)

## Local development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Docker (for Postgres).

```bash
cp .env.example .env
make install   # create .venv, install dependencies and git hooks (pre-commit)
make db        # start Postgres in Docker
make dev       # migrate and run the dev server on :8000
make test      # run tests with coverage
make lint      # ruff check + format check
```

## API overview

All endpoints live under `/api/v1/`. Send the access token as `Authorization: Bearer <token>`.

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/auth/register/` | Create an account | – |
| POST | `/auth/token/` | Get access + refresh tokens | – |
| POST | `/auth/token/refresh/` | Get a new access token | – |
| GET / PATCH | `/auth/me/` | View or update your profile | ✅ |
| GET / POST | `/categories/` | List or create your categories | ✅ |
| GET / PATCH / DELETE | `/categories/{id}/` | View, rename or delete one of your categories | ✅ |

Example:

```bash
curl -X POST localhost:8000/api/v1/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"email": "ana@example.com", "password": "S3cure-pass!"}'

curl -X POST localhost:8000/api/v1/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"email": "ana@example.com", "password": "S3cure-pass!"}'
```

## Project structure

```
config/
  settings/        base.py (shared), dev.py, test.py, prod.py
  urls.py          API v1 routes, OpenAPI schema and docs
apps/
  core/            cross-cutting pieces (health check)
  users/           custom User model, registration, JWT endpoints
    services.py    business logic (writes)
    tests/
  expenses/        categories (and soon expenses), always scoped to the current user
```

Views and serializers stay thin; business rules live in `services.py`, so they can be
tested without HTTP.

Every query for user data starts from `request.user` (e.g. `request.user.categories`), so a
user can never read or change another user's data: those ids simply return `404`. Tests
check this for every method.

## CI

Every pull request and push to `main` runs:

1. **Lint**: Ruff (style and common bugs).
2. **Test**: pending-migrations check, `check --deploy` against production settings, and the
   test suite with coverage against a real PostgreSQL service.
3. **Docker**: builds the production image.
