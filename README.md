# Expense Tracker API

[![CI](https://github.com/SEDEBE/expense-tracker-api/actions/workflows/ci.yml/badge.svg)](https://github.com/SEDEBE/expense-tracker-api/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.14-blue)
![Django](https://img.shields.io/badge/django-5.2_LTS-green)

REST API to track personal expenses: register, log in with JWT, record expenses by category
and get monthly summaries.

It is the backend of a full-stack project:

- **Frontend**: [expense-tracker-web](https://github.com/SEDEBE/expense-tracker-web) (React + TypeScript), with a one-click demo account.
- **Production setup**: [portfolio-infra](https://github.com/SEDEBE/portfolio-infra) (Docker Compose, Caddy with automatic HTTPS, images on GHCR, deployment from CI over SSH, nightly backups).

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.14, Django 5.2 LTS, Django REST Framework |
| Auth | JWT (`djangorestframework-simplejwt`), email-based custom user, Sign in with Google (`google-auth`) |
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
| POST | `/auth/demo/` | Create a throwaway demo account with sample data and get its tokens | – |
| POST | `/auth/google/` | Log in or sign up with a Google ID token and get tokens | – |
| POST | `/auth/password-reset/` | Email a link to reset the password (same answer whether the account exists or not) | – |
| POST | `/auth/password-reset/confirm/` | Set a new password with the `uid` and `token` from that link | – |
| GET / PATCH | `/auth/me/` | View or update your profile | ✅ |
| GET / POST | `/categories/` | List or create your categories | ✅ |
| GET / PATCH / DELETE | `/categories/{id}/` | View, rename or delete one of your categories | ✅ |
| GET / POST | `/expenses/` | List (filtered, sorted, paginated) or create your expenses | ✅ |
| GET / PATCH / DELETE | `/expenses/{id}/` | View, edit or delete one of your expenses | ✅ |
| GET | `/expenses/summary/?month=YYYY-MM` | Monthly total and totals by category (defaults to the current month) | ✅ |
| GET | `/expenses/history/?months=6` | Total of each of the last N months (1–24), oldest first, empty months as zero | ✅ |
| GET, POST | `/recurring/` | List or create recurring expenses (amount, description, category, `day_of_month` 1–31) | ✅ |
| GET, PATCH, DELETE | `/recurring/{id}/` | One recurring expense; `active: false` pauses it | ✅ |
| GET | `/expenses/export/` | Expenses as CSV, with the list's filters and ordering (`;` and decimal commas in Spanish, for Excel) | ✅ |
| POST | `/expenses/summary/email/` | Email me the summary of `{"month": "YYYY-MM"}` now (current month by default; 5 per hour, not for demo accounts) | ✅ |

Expense list filters: `date_from`, `date_to`, `amount_min`, `amount_max`, `category`,
`uncategorized=true`, and `ordering` by `date`, `amount` or `created_at` (prefix `-` for
descending). Example: `/expenses/?date_from=2026-10-01&date_to=2026-10-31&ordering=-amount`.

Deleting a category keeps its expenses; they become uncategorized. Amounts must be
positive, which is enforced both by the API and by a database constraint. An expense's
category must belong to the same user, which is checked by the API and by model validation
(so the admin enforces it too).

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

### Demo accounts

`POST /auth/demo/` gives every visitor their own throwaway account, so nobody sees what
another visitor changed. It comes with categories and six months of realistic expenses in
Spanish, and the response has the same tokens as `/auth/token/`.

- Demo accounts have no usable password: the endpoint is the only way in.
- They are flagged with `is_demo` (also returned by `/auth/me/`) and never get emails.
- A Celery beat task deletes them every hour once they are older than `DEMO_USER_TTL_HOURS`
  (24 by default), together with their data.
- Each call creates a user, so it is limited to 10 per hour per IP. Behind a reverse proxy,
  set `NUM_PROXIES` so the limit sees the client's IP and not the proxy's.
- Turned on with `DEMO_ENABLED=True`; when it is off the endpoint returns `404`.

### Sign in with Google

The frontend shows Google's button, which returns a signed ID token. `POST /auth/google/` with
`{"credential": "<token>"}` checks the token with Google's public keys (signature, expiry and
that it was issued for this app's `GOOGLE_CLIENT_ID`) and returns the same JWT pair as
`/auth/token/`.

- An existing account with the same email logs in; otherwise a new one is created without a
  usable password. Google must have verified the email.
- Get a client ID in Google Cloud console → APIs & Services → Credentials → OAuth client ID
  (type "Web application"), with the frontend's origins as authorized JavaScript origins. It is
  free. Leave `GOOGLE_CLIENT_ID` empty to turn the endpoint off (`404`).

### Password reset

`POST /auth/password-reset/` with an email sends, through Celery, a link to
`FRONTEND_URL/restablecer?uid=…&token=…` in the user's language. The answer is the same whether or
not an account uses that email, so it cannot be used to find out who is registered; demo accounts
are skipped. The token comes from Django's `default_token_generator`: it expires after two hours
(`PASSWORD_RESET_TIMEOUT`) and stops working once the password changes. Both endpoints are limited to
5 requests per hour per IP.

### Calling the API from a frontend

Browsers block requests to another origin unless the API allows it (CORS). Allowed origins
come from `CORS_ALLOWED_ORIGINS`, a comma-separated list in `.env`. `.env.example` allows
the Vite dev server:

```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

Nothing is allowed by default, and credentials (cookies) are not allowed because
authentication uses the `Authorization` header.

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

## Budgets

Each category can have a monthly budget (`monthly_budget`, empty means none). After an expense is
saved, a Celery task checks its category: when this month's spending reaches 80% and then 100% of
the budget, the user gets an email. Each threshold is sent once per category and month
(`BudgetAlert` records what was sent), and a jump past both sends only the 100% one. The task runs
after the database commit, so the API answers without waiting for it.

## Recurring expenses

Rent, subscriptions and other fixed costs are saved once as recurring expenses. Every day at
05:30 UTC a Celery beat task creates the real expense of each one that is due and moves its
`next_date` to the next month. Day 31 falls on the last day of shorter months, a missed run is
caught up with the right dates, running twice never duplicates (each row is locked while it is
processed), and new expenses go through the budget check like any other.

## Error tracking

In production, setting `SENTRY_DSN` reports unhandled errors from requests and Celery tasks to
[Sentry](https://sentry.io) with their stack trace, and times a 10% sample of requests. No personal
data is sent (`send_default_pii=False`). Without the variable, nothing is reported.

## Monthly summary emails

On the first day of each month at 07:00 UTC, every active user who had expenses in the
previous month gets an email with their summary, in their own language. Emails are sent as plain
text plus an HTML version (`apps/core/templates/emails/`) that looks like the app.
Users can also ask for it at any time from the dashboard (`POST /expenses/summary/email/`): the
API answers at once with `202 Accepted` and a Celery worker sends the email, retrying if the mail
server fails for a moment.

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
  demo/            throwaway demo accounts
    data.py        sample categories and expenses
    services.py    create demo users and delete expired ones
    tasks.py       hourly cleanup task
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
3. **Docker**: builds the production image; on `main` it is also published to GHCR
   (`ghcr.io/sedebe/expense-tracker-api`).
4. **Deploy** (only on `main`, once the server is configured): pulls the new image on the
   server and restarts the API, worker and beat.
