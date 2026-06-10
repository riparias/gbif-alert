# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GBIF Alert is a Django-based early alert system for invasive species using GBIF data. It monitors species and notifies users of new occurrences via email. The primary production instance is LIFE RIPARIAS Early Alert (https://alert.riparias.be).

## Tech Stack

- **Backend:** Python 3.12+, Django 5.2 (GeoDjango), PostgreSQL/PostGIS 3.1+, Redis/Valkey (django-rq)
- **Frontend:** TypeScript, Vue.js 3, PrimeVue (Aura preset), Vue Router, Pinia, OpenLayers (maps), D3.js (charts)
- **Build tools:** uv (Python), npm + Vite (frontend)

## Commands

### Django Settings
To run `manage.py` commands (makemigrations, migrate, test, etc.), set the Django settings module:
```bash
export DJANGO_SETTINGS_MODULE=djangoproject.local_settings
```

### Setup
```bash
uv sync                 # Install Python dependencies
npm install             # Install frontend dependencies
```

### Development
```bash
npm run vite-dev                           # Start Vite dev server (HMR)
uv run python manage.py runserver        # Start Django dev server
uv run python manage.py rqworker default # Start Redis queue worker
```

### Testing & Type Checking
```bash
uv run python manage.py test                        # Run all Django tests
uv run python manage.py test dashboard.tests.models # Run specific test module
uv run python manage.py test dashboard.tests.commands.test_import_observations # Import tests
uv run mypy .                                       # Type checking
```

### Code Formatting
```bash
black .       # Format Python code (always run after changes)
prettier      # Format JS/TS/Vue code (configure editor for format-on-save)
```

### Translations
```bash
uv run python manage.py makemessages --ignore="node_modules/*" -l fr -l nl  # Update PO files
uv run python manage.py compilemessages                                      # Compile MO files
```

### Key Management Commands
```bash
uv run python manage.py import_observations              # Import GBIF occurrence data
uv run python manage.py send_alert_notifications_email   # Send notification emails
uv run python manage.py refresh_materialized_views       # Refresh DB materialized views
uv run python manage.py migrate_new_seen_unseen          # Update seen/unseen status
uv run python manage.py load_area <source_file>          # Import geographic area
```

### Production Build
```bash
npm run vite-build      # Build optimized frontend bundle
```

### Regenerate TypeScript types (after any API change)
```bash
npm run generate-types  # Exports OpenAPI schema, writes assets/frontend/types/api.ts
```

## Architecture

### Django Apps
- **`dashboard/`** — Main app containing all core logic: models, views, templates, management commands, and tests
- **`page_fragments/`** — Small app for admin-editable page content blocks (uses `templatetags` for rendering)
- **`djangoproject/`** — Django project settings; instance-specific configuration goes in `local_settings.py` (copied from `local_settings.template.py`)

### Configuration System
Each GBIF Alert instance is configured via `local_settings.py` which contains a `GBIF_ALERT` dict with site name, colors, enabled languages, GBIF download credentials, and a `PREDICATE_BUILDER` function that defines the GBIF search query. This is how different instances target different species/regions.

### Frontend-Backend Integration
Single-page application: all pages are served by the `spa_shell` Django view, which injects a `gbif-alert-nav-config` JSON block (site name, enabled languages, auth state) and loads the Vite bundle. Vue Router (history mode) handles client-side routing. Pinia manages shared state (active filters). A Django catch-all pattern in `djangoproject/urls.py` forwards unmatched paths to the SPA shell.

The API layer is Django Ninja at `/api/v2/`. Schemas live in `dashboard/api_v2_schemas.py`. TypeScript types are auto-generated from the OpenAPI spec via `npm run generate-types` and committed to `assets/frontend/types/api.ts`.

Frontend source lives entirely in `assets/frontend/` (Vite-managed). The old `assets/ts/` directory has been removed.

### Views Organization (`dashboard/views/`)
- `pages.py` — `spa_shell` view + legacy page stubs
- `maps.py` — Map tile endpoints (still used by the SPA map components)
- `api_v2.py` — Django Ninja v2 API (main API for the SPA)
- `public_api.py` — Legacy public REST API (WFS + some endpoints; partially superseded by v2)

### Observation Import Pipeline (`import_observations` command)
This is the most critical and performance-sensitive process. It:
1. Triggers a GBIF download based on the configured predicate
2. Processes the Darwin Core Archive file
3. Loads observations into the database in a single transaction
4. Deletes observations from previous imports to avoid duplicates
5. Runs in maintenance mode (site unavailable during import)

Optimizations are documented in `IMPORT_OBSERVATIONS_OPTIMIZATION.md`. Batch database operations to avoid N+1 queries.

### Observation Identity
Observations are identified across imports by `stable_id` — a SHA1 hash of `occurrence_id` + `dataset_key`. When an observation is re-imported, comments and seen/unseen status are migrated from the old record to the new one via `replaced_observation`.

### Seen/Unseen Status
`ObservationUnseen` records track which observations each user hasn't seen. An observation is "unseen" if it matches a user's alert AND is newer than their notification delay setting. The `migrate_unseen_observations()` function updates these during import.

### Internationalization
- Backend/templates: Standard Django i18n (`gettext`, `trans` template tag). Supported locales: English, French, Dutch.
- Vue components: `vue-i18n` with translations in `assets/frontend/translations.ts` (keep keys alphabetically sorted)
- Database content: Translated via `django-modeltranslation` in Django Admin

### Background Tasks
Redis + django-rq handles long-running tasks (e.g., "mark all observations as seen"). Run a worker with `python manage.py rqworker default`.

### GIS/WFS
The app provides an OGC Web Feature Service endpoint at `/api/wfs/observations` via `django-gisserver`.

## Branching & Deployment
- Never commit directly to `main`
- Feature branches → merge to `devel` → auto-deploys to demo server → merge to `main` → manual production deploy via `deploy_main.sh`
- CI runs Django tests + mypy on every push (GitHub Actions)

## Version Bumping
Version number must be updated in three places: `pyproject.toml`, `package.json`, and `docker-compose.yml` (3 services: gbif-alert, rqworker, nginx).

## Code Style
- Python: `black` formatting, imports at top of file (stdlib → third-party → local), avoid local imports unless circular dependency
- JS/TS/Vue: `prettier` formatting