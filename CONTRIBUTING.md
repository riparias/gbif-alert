# Development setup and notes

## Technological backbone
- [Python](https://www.python.org/) 3.13+, [(Geo)Django](https://www.djangoproject.com/) 5.2, [PostgreSQL](https://www.postgresql.org/), [PostGIS](https://postgis.net/) 3.1+, [Redis](https://redis.io/) (or [Valkey](https://valkey.io/)), [TypeScript](https://www.typescriptlang.org/) and [Vue.js v3](https://vuejs.org/)
- UI components: [PrimeVue](https://primevue.org/) v4
- [uv](https://docs.astral.sh/uv/) is used to manage dependencies (use `uv add`, `uv sync`, ... instead of pip).

## Dev environment configuration
- Python>=3.13, PostGIS>=3.1, Redis (or Valkey) and `npm` are required
- Use [uv](https://docs.astral.sh/uv/) to create an isolated virtualenv and install dependencies (`uv sync`)
- Configure the app via environment variables. Copy `.env.example` at the project root to `.env` and fill in the values:
   ```
   cp .env.example .env
   $EDITOR .env
   ```
   For dev, you typically want:
   ```
   DEBUG=True
   SECRET_KEY=anything-not-empty
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   SITE_BASE_URL=http://localhost:8000
   SITE_NAME=GBIF Alert (dev)
   DATABASE_URL=postgis://gbif:gbif@localhost:5432/gbif_alert_dev
   RQ_REDIS_URL=redis://localhost:6379/0
   ```
- For settings that cannot be expressed as env vars (e.g. a custom `PREDICATE_BUILDER` callable), copy `djangoproject/local_settings.template.py` to `djangoproject/local_settings.py` and edit. This file is gitignored and imported as an escape hatch after the env-driven settings.
- Django is pointed at `djangoproject.settings` (the canonical entry point - it loads `.env`, then reads env vars, then imports `local_settings.py` as the escape hatch).

## Testing / typing
This project provides the following tools to ensure the application and code stays in a decent state:

### Running all tests (`pytest`)

All tests - Django unit tests, API tests, and Playwright browser tests - run via a single command:

```
$ pytest
```

pytest is configured in `pyproject.toml` (`testpaths = ["dashboard/tests"]`). The command automatically runs `npm run vite-build` before the tests start, so the Playwright tests always have an up-to-date frontend bundle.

To run a single test file:

```
$ pytest dashboard/tests/models/test_alert.py
```

To run a single test:

```
$ pytest dashboard/tests/models/test_alert.py::test_has_unseen_observations_true
```

> **Note:** tests run with `DJANGO_SETTINGS_MODULE=djangoproject.settings` (configured in `pyproject.toml` under `[tool.pytest.ini_options]`). Safe test env defaults (DB URL, GBIF creds, etc.) are provided via the `pytest-env` plugin in the same section, so a clean checkout can run tests without any local `.env`. Your own `.env` (if present) takes precedence.

### Typing

Can be checked with `$ mypy .`

Those should be run frequently on the developer's machines, but will also be executed by GitHub actions each time the code is pushed to GitHub (see the CI-CD section)

## CI-CD

We make use of GitHub Actions when possible. They're currently used to:

- Run Django tests and `mypy` on every push
- Automatically deploy the `devel` branches to the respective server when code is pushed (see `Working with 
  branches` below) 

## Working with branches

While deployment in production is currently manually run, it's crucial to keep it in an "always 
deployable" state and code should **never** be committed directly to the `main` branch.

The current workflow is:

1) New features and bug fixes are implemented in their own specific branches (created from `main`). 
2) After being checked locally and deemed satisfactory, the new branch is merged to `devel`
3) `devel` is pushed to GitHub: the updated version can be tested on the development server and shared with stakeholders.
4) after everything is confirmed ok, the `devel` branch is merged to `main`
5) `main` is pushed to GitHub
6) a release is published by tagging `v*` (see "How to release a new version" below); production rolls forward by bumping `GBIF_ALERT_TAG` to the new image (see INSTALL.md "Upgrades")

For small, non-risky changes, steps 1-3 can be avoided by committing directly to the `devel` branch.

## Dependencies

We try to frequently update dependencies. Process is:

- Backend: `$ uv lock --upgrade`
- Frontend: `$ npm-check -u`
- Run unit tests (+ a few manual checks?)
- Commit changes (should include `package.json`, `package-lock.json` and `uv.lock`)

## Frontend-backend integration

The frontend is a Vue 3 single-page application managed by Vite. All pages are served
by the `spa_shell` Django view; Vue Router handles client-side routing.

Frontend source lives in `./assets/frontend/`. The main entry point is `main.ts`.

- npm is used to manage JS dependencies (**npm install** should be run once)
- **During development**, run `npm run vite-dev` to start the Vite dev server (required for HMR)
- **When deploying**, use `npm run vite-build` to produce hashed assets in `./static_global/vite`

### API v2 (Django Ninja)

The new API lives at `/api/v2/` and is built with [Django Ninja](https://django-ninja.dev/).
It is being introduced incrementally as part of the frontend migration.

Django Ninja auto-generates interactive API documentation from the endpoint definitions and
response schemas. While the dev server is running, these are available at:

- **Interactive docs (Swagger UI):** http://localhost:8000/api/v2/docs
- **OpenAPI JSON schema:** http://localhost:8000/api/v2/openapi.json

The OpenAPI JSON schema is also used to generate TypeScript types for the new frontend
via `openapi-typescript`. Run after any API change:

```
$ npm run generate-types
```

This exports the schema from Django (no server required) into `openapi-schema.json`
(gitignored), then generates `assets/frontend/types/api.ts` (committed).
Re-run and commit `api.ts` whenever an endpoint or schema changes.

Endpoints are defined in `dashboard/api_v2.py`; response schemas in `dashboard/api_v2_schemas.py`.

## Code formatting

We use `black` (for Python code) and `prettier` (for JS/TS/Vue) to automatically and consistently format the source code.
Please configure your favorite editor/IDE to format on save. 

## Observation import mechanism

The observation data shown in the webapp can be automatically updated by running the `import_observations` management 
command. This one will trigger a GBIF Download for our search of interest (based on the predicate builder function from the config file) and 
load the corresponding observations into the database. At the end of the process, observations from previous data 
imports are deleted, to avoid duplicates.

The data import history is recorded with the DataImport model, and shown to the user on the "about" page.

=> For a given observation, Django-managed IDs are therefore not stable. A hashing mechanism (based on `occurrenceId` 
and `DatasetKey`) to allow recognizing a given observation is implemented (`stable_id` field on Observation).

## Areas import mechanism

The application allows storing Areas (multipolygons) in the database for observation filtering and to display as map 
overlays. Each area can be either user-specific, either public. For now, there are 
3 ways to load a new area in the system:

- Administrators can use the Admin section to hand-drawn the area over an OSM background
- Administrators with a shell access The custom `load_area` management command can be used to directly import complex polygons from a file 
  source (shapefile, GeoJSON, ...)
- Users can upload their own areas via the web interface (development in progress
  
### How to use the `load_area` command to import a new public Area

1) Copy the source data file to `source_data/public_areas`
2) Adjust the `LAYER_MAPPING_CONFIGURATION` constant in `load_area.py` so it can deal with the specificities 
   of the new source file (other adjustments to `load_area.py` may also be necessary, see 
   [LayerMapping documentation](https://docs.djangoproject.com/en/3.2/ref/contrib/gis/layermapping/).)
3) Run `$ python manage.py load_area <my_source_file>`


## Users

The web application handle three categories of users:

- Anonymous users can access the website and visualize the observation data via the dashboard. For Django, they are 
  unauthenticated.
- Registered "normal" users can do all what can anonymous users can do + create and configure their alerts. Those users can 
  sign up directly thanks to a specific form (an e-mail address is required because it is needed for e-mail 
  notifications). For Django, they are regular users without any specific group or permission (**not** 
  staff, **not** superuser)
- Admins can do all that registered users can do + access the admin interface to configure the web application. For 
  Django, they have the **staff** and **superuser** flags set. Admins can be created by different means, for example 
  being upgraded to this status by an existing Admin after registering as a normal user, or via Django's 
  `createsuperuser` management command.
  
## Use of Redis

Redis/Valkey is a hard local-dev dependency. It's used for two things:

1. With [django-rq](https://github.com/rq/django-rq) to manage queues for long-running tasks (as of 2023-08: mark all observations as seen).
2. As Django's cache backend, which `django-maintenance-mode` uses to share the maintenance flag across processes (gunicorn workers, the rqworker container, the `import_observations` command, and `manage.py maintenance_mode on/off` from your terminal).

Install a Redis or Valkey instance on your development machine and make sure it's listening on the default `localhost:6379`. On macOS the easiest path is `brew install valkey && brew services start valkey`. The Django settings default to `redis://localhost:6379/0` for both the cache and the RQ broker, so no env vars are needed for the standard setup; override `RQ_REDIS_URL` (and optionally `CACHE_URL`) in your `.env` if you run it elsewhere or want to isolate the cache on a different Redis DB.

Then run a worker for the default queue with `$ python manage.py rqworker default`.

If you skip this step:

- `manage.py runserver` will still render pages because `CacheBackend` swallows cache errors and falls back to "not in maintenance mode", but every request logs a warning and `manage.py maintenance_mode on` silently no-ops.
- RQ features (queued jobs, scheduled imports run via `rqworker`) won't work at all.

## Maintenance mode

We make use of [django-maintenance-mode](https://github.com/fabiocaccamo/django-maintenance-mode), configured with its `CacheBackend` so the flag is shared across all processes through the Django cache (see above).

Maintenance mode will be set during each (observation) data import (data would be inconsistent at this stage, so we don't
want to let users access the website, nor send e-mail notifications).

This tool can also be used to manually activate maintenance mode during complex maintenance tasks, look at 
[django-maintenance-mode documentation](https://github.com/fabiocaccamo/django-maintenance-mode).

If the cache is misconfigured or unreachable in production, `CacheBackend` logs a warning and returns `MAINTENANCE_MODE_STATE_BACKEND_FALLBACK_VALUE` (set to `False` in `settings.py`) - so a Valkey outage degrades to "site stays up, maintenance toggle silently no-ops" rather than 5xx-ing every request.

## Internationalization (i18n)

- For template-based / backend translations, we use the standard Django i18n tools (see [Django documentation](https://docs.djangoproject.com/en/4.1/topics/i18n/)) 
- (don't forget the translation for the notification e-mails: see `dashboard/templates/dashboard/emails` )
- For Vue components, we use https://vue-i18n.intlify.dev/ instead.
- Data-related translations that should be provided directly in the database via Django Admin: page fragments, vernacular names, ...

### How to update translations: Django
- In code, use the appropriate `gettext` functions (e.g. `_()`, `gettext()`, `ngettext()`, etc.), the `trans` template tag, etc.
- Update PO files with `$ python manage.py makemessages --ignore="node_modules/*" -l fr -l nl`
- Fill in the translations in the PO files
- Compile the PO files to MO with `$ python manage.py compilemessages`

### How to update translations: Vue
- Update the `messages` object in assets/frontend/translations.ts. Please keep the keys in alphabetical order.

## How to release a new version

Releases are built and published automatically by `.github/workflows/release.yml`
when a `v*` tag is pushed: the image is pushed to GHCR
(`ghcr.io/riparias/gbif-alert`) and stamped with the tag, which the footer
displays. No manual `VERSION` file edit is needed.

1. Make sure all tests pass and `mypy` reports no errors.
2. Update `CHANGELOG.md`.
3. (Optional) Bump the version in `pyproject.toml` for metadata consistency.
   It is no longer load-bearing for the footer (`package.json` no longer
   carries a version).
4. Commit, merge to `main`, push.
5. Tag and push:
   ```
   $ git tag v1.1.0
   $ git push origin v1.1.0
   ```
   This triggers `release.yml`, which builds and pushes
   `ghcr.io/riparias/gbif-alert:1.1.0` (and `:latest`), stamped with the tag.
6. Bump `GBIF_ALERT_TAG` on each instance (see INSTALL.md "Upgrades") to roll
   the new image out.

The footer version is auto-stamped: release images show the tag (`v1.1.0`);
`devel`/`main` images show a `git describe` string (e.g. `v1.0.0-42-gabc123`).

## How to link to a GBIF alert instance with specific filters

The index page (`/`) reads filters from URL query parameters. All parameters are optional and can be combined.

| Parameter               | Type                            | Example                          |
|-------------------------|---------------------------------|----------------------------------|
| `speciesIds`            | integer (repeatable)            | `speciesIds=2&speciesIds=14`     |
| `datasetsIds`           | integer (repeatable)            | `datasetsIds=5`                  |
| `basisOfRecordIds`      | integer (repeatable)            | `basisOfRecordIds=1`             |
| `areaIds`               | integer (repeatable)            | `areaIds=1`                      |
| `initialDataImportIds`  | integer (repeatable)            | `initialDataImportIds=3`         |
| `startDate` / `endDate` | date string                     | `startDate=2024-01-01`           |
| `status`                | `seen` / `unseen` / `all`       | `status=all`                     |
| `verifiedFilter`        | `verified` / `unverified` / `all` | `verifiedFilter=verified`      |
| `areaFilterMode`        | `inside` / `approaching` / `both` | `areaFilterMode=approaching`   |
| `approachingDistanceKm` | float                           | `approachingDistanceKm=5.0`      |

Examples:

- `https://alert.riparias.be/?speciesIds=2&speciesIds=14&speciesIds=15`
- `https://alert.riparias.be/?speciesIds=2&areaIds=1`