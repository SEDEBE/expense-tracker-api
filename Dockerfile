# syntax=docker/dockerfile:1

# ---- Build stage: resolve and install dependencies with uv ----
FROM ghcr.io/astral-sh/uv:0.12-python3.14-trixie-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# Install deps first, in their own layer, so code changes don't invalidate the cache.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project
COPY . .
RUN SECRET_KEY=build-only DATABASE_URL=sqlite:////tmp/build.db \
    .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.prod

# ---- Runtime stage: only the venv and the code, no build tools ----
FROM python:3.14-slim-trixie
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" DJANGO_SETTINGS_MODULE=config.settings.prod
RUN groupadd --system app && useradd --system --gid app --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')"
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
