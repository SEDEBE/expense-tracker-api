# Expense Tracker API

[![CI](https://github.com/SEDEBE/expense-tracker-api/actions/workflows/ci.yml/badge.svg)](https://github.com/SEDEBE/expense-tracker-api/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.14-blue)
![Django](https://img.shields.io/badge/django-5.2_LTS-green)

REST API to track personal expenses: register, log in with JWT, record expenses by category
and get monthly summaries.

> 🚧 Work in progress. Done so far: project setup, users and JWT auth, categories, expenses, monthly summaries, summary emails and English/Spanish support, and monthly emails scheduled with Celery. Next: a live deployment and a frontend.

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.14, Django 5.2 LTS, Django REST Framework |
| Auth | JWT (`djangorestframework-simplejwt`), email-based custom user |
| Database | PostgreSQL 18 |
| Background jobs | Celery 5.6 (worker + beat) with Redis 8 as the broker, Mailpit as a local test inbox |
| API docs | OpenAPI 3 with `drf-spectacular` (Swagger UI) |
| i18n | Django gettext: English and Spanish, negotiated with `Accept-Language` |
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
- Test inbox (Mailpit): http://localhost:8025 (every email the app sends lands here)

`docker compose up` starts the API, a Celery worker, Celery beat, PostgreSQL, Redis and Mailpit.

## Local development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/), Docker (for Postgres,
Redis and Mailpit) and GNU gettext to compile translations (`sudo apt install gettext` on
Debian/Ubuntu).

```bash
cp .env.example .env
make install   # create .venv, install dependencies and git hooks (pre-commit)
make db        # start Postgres, Redis and Mailpit in Docker
make dev       # migrate and run the dev server on :8000
make worker    # run a Celery worker (in another terminal)
make beat      # run Celery beat, the scheduler (in another terminal)
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
| GET / POST | `/expenses/` | List (filtered, sorted, paginated) or create your expenses | ✅ |
| GET / PATCH / DELETE | `/expenses/{id}/` | View, edit or delete one of your expenses | ✅ |
| GET | `/expenses/summary/?month=YYYY-MM` | Monthly total and totals by category (defaults to the current month) | ✅ |

Expense list filters: `date_from`, `date_to`, `amount_min`, `amount_max`, `category`,
`uncategorized=true`, and `ordering` by `date`, `amount` or `created_at` (prefix `-` for
descending). Example: `/expenses/?date_from=2026-10-01&date_to=2026-10-31&ordering=-amount`.

Deleting a category keeps its expenses; they become uncategorized. Amounts must be
positive, which is enforced both by the API and by a database constraint.

The monthly summary is computed in the database with two queries, whatever the number of
expenses. Amounts are returned as strings to keep decimal precision:

```json
{
  "month": "2026-10",
  "total": "25.00",
  "by_category": [
    {"category_id": 3, "category": "Food", "total": "20.50", "count": 1},
    {"category_id": null, "category": null, "total": "4.50", "count": 1}
  ]
}
```

Example:

```bash
curl -X POST localhost:8000/api/v1/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"email": "ana@example.com", "password": "S3cure-pass!"}'

curl -X POST localhost:8000/api/v1/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"email": "ana@example.com", "password": "S3cure-pass!"}'
```

## Languages

The API and the emails are available in English (default) and Spanish.

- **API responses** follow the `Accept-Language` header (e.g. `Accept-Language: es`): error
  messages, both Django's and the project's own, come back translated, and the response
  says which language it used in `Content-Language`.
- **Emails** use each user's `language` (`en` or `es`), since they are sent outside any
  request. It defaults to the language negotiated at registration and can be changed with
  `PATCH /auth/me/`. Month names and numbers are localized too (`octubre de 2026`, `25,00`).

Translations live in `locale/es/LC_MESSAGES/django.po`. Only the `.po` file is committed;
the `.mo` file Django reads is compiled by `make dev`/`make test`, CI and the Docker build.

```bash
make messages          # extract new translatable strings into the .po file
make compilemessages   # compile the .po file
```

## Monthly summary emails

On the first day of each month at 07:00 UTC, every active user who had expenses in the
previous month gets an email with their summary, in their own language.

```mermaid
flowchart LR
    beat[Celery beat] -- "1st of month, 07:00 UTC" --> redis[(Redis)]
    redis --> worker[Celery worker]
    worker --> db[(PostgreSQL)]
    worker -- SMTP --> mail[Mailpit / SMTP server]
```

- **beat** only decides *when*: it puts a message on Redis. Run exactly one.
- **worker** does the work: it reads the message, queries PostgreSQL and sends the emails.
- With Docker Compose, emails go to **Mailpit** (http://localhost:8025), so nothing reaches
  real inboxes.

The same logic can be run by hand:

```bash
uv run python manage.py send_monthly_summaries                 # previous month
uv run python manage.py send_monthly_summaries --month 2026-09 # a specific month

# With Docker
docker compose exec api python manage.py send_monthly_summaries
```

`EMAIL_URL` chooses where emails go: `consolemail://` (the default) prints them to the
console, and `smtp+tls://user:password@host:587` sends them through an SMTP server. Set
`DEFAULT_FROM_EMAIL` to change the sender.

## Project structure

```
config/
  settings/        base.py (shared), dev.py, test.py, prod.py
  urls.py          API v1 routes, OpenAPI schema and docs
  celery.py        Celery app (reads CELERY_* settings, finds every app's tasks.py)
apps/
  core/            cross-cutting pieces (health check)
  users/           custom User model, registration, JWT endpoints
    services.py    business logic (writes)
    tests/
  expenses/        categories and expenses, always scoped to the current user
    filters.py     expense list filters (django-filter)
    selectors.py   read-only queries (monthly summary) and month helpers
    services.py    business logic (summary emails)
    tasks.py       Celery task that sends the monthly summaries
    management/    send_monthly_summaries command
locale/            Spanish translations (.po)
```

Views and serializers stay thin: writes live in `services.py` and non-trivial reads in
`selectors.py`, so business logic can be tested without HTTP.

Every query for user data starts from `request.user` (e.g. `request.user.categories`), so a
user can never read or change another user's data: those ids simply return `404`. Tests
check this for every method.

## CI

Every pull request and push to `main` runs:

1. **Lint**: Ruff (style and common bugs).
2. **Test**: compiles translations, checks for pending migrations, runs `check --deploy`
   against production settings, and runs the test suite with coverage against a real
   PostgreSQL service.
3. **Docker**: builds the production image.
