# syntax=docker/dockerfile:1.7

# ============================================================================
# Stage 1: frontend build
# ============================================================================

FROM node:20-bookworm-slim AS frontend
WORKDIR /build

# Install npm deps (separate layer for cache-friendliness).
# `--include=optional` works around npm/cli#4828, where platform-specific
# native bindings (rolldown, esbuild, etc.) listed as optional deps are
# sometimes skipped when the lock file was generated on a different host.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --include=optional

# Build the Vite bundle. Output goes to /build/static_global/vite/.
COPY assets/ assets/
COPY vite.config.ts tsconfig*.json ./
RUN npm run vite-build

# ============================================================================
# Stage 2: final runtime image
# ============================================================================

FROM python:3.11-slim AS app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    DJANGO_SETTINGS_MODULE=djangoproject.settings

# Runtime system deps:
#  - libgdal-dev: GeoDjango bindings link against it; the runtime needs
#    the shared library (the headers come along, slightly oversized).
#  - gettext: needed by `manage.py compilemessages` at build time.
#  - curl: handy for ad-hoc healthchecks; small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev \
        gettext \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps in a separate layer (cache-friendly: only invalidates when
# pyproject.toml or poetry.lock changes).
RUN pip install "poetry==${POETRY_VERSION}"
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# Application source.
COPY . .

# Built frontend assets from Stage 1 (overlays whatever was in the source).
COPY --from=frontend /build/static_global/vite ./static_global/vite

# Build-time Django steps. Dummy env vars so settings.py loads without
# raising ImproperlyConfigured.
RUN SECRET_KEY=build-only \
    DATABASE_URL=sqlite:///tmp/build.sqlite3 \
    DJANGO_ALLOWED_HOSTS=localhost \
    SITE_BASE_URL=http://localhost \
    SITE_NAME=build \
    poetry run python manage.py collectstatic --noinput && \
    SECRET_KEY=build-only \
    DATABASE_URL=sqlite:///tmp/build.sqlite3 \
    DJANGO_ALLOWED_HOSTS=localhost \
    SITE_BASE_URL=http://localhost \
    SITE_NAME=build \
    poetry run python manage.py compilemessages

# Non-root user.
RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app && \
    chown -R app:app /app
USER app

EXPOSE 8000

# Shell-form CMD so ${GUNICORN_WORKERS:-3} is expanded at runtime. tini
# (provided by `init: true` in compose, or `--init` for `docker run`) is
# PID 1 for clean signal handling.
CMD gunicorn djangoproject.wsgi \
        --bind 0.0.0.0:8000 \
        --workers ${GUNICORN_WORKERS:-3} \
        --access-logfile - \
        --error-logfile -
