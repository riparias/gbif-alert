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

FROM python:3.13-slim AS app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DJANGO_SETTINGS_MODULE=djangoproject.settings \
    PATH="/app/.venv/bin:$PATH"

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

# uv binary from the official distroless image (pinned).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Python deps in a cache-friendly layer (invalidates only when
# pyproject.toml or uv.lock changes). --no-install-project: the app is
# package-mode=false. --no-dev: runtime image excludes dev deps.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

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
    python manage.py collectstatic --noinput && \
    SECRET_KEY=build-only \
    DATABASE_URL=sqlite:///tmp/build.sqlite3 \
    DJANGO_ALLOWED_HOSTS=localhost \
    SITE_BASE_URL=http://localhost \
    SITE_NAME=build \
    python manage.py compilemessages

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
