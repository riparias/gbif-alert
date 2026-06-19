# 2.0.2 (2026-06-19)

- Fix: the observations map now honors the "viewed / not viewed" status filter.
  The map tile endpoints received the frontend's "viewed"/"notViewed" status
  values but only recognized the internal "seen"/"unseen", so the filter was
  silently dropped: the map showed every observation regardless of status while
  the counter, histogram, and table updated correctly. The status vocabulary
  mapping now lives in a single place shared by the v2 API and the map tile
  endpoints, so they cannot drift apart again.

# 2.0.1 (2026-06-19)

- Fix: the compose files now declare service `labels:` in list form so Dokploy's
  Domains tab injects its Traefik routing labels (it silently skips map-form
  labels). A Compose deployment now routes via the Domains tab with no manual
  Traefik file-provider config. Application code is unchanged - the image is
  identical to 2.0.0.

# 2.0.0 (2026-06-18)

GBIF Alert 2.0 is a major release: a brand-new user interface, a modern
public API, and a fully reworked Docker/deployment stack.

## A new user interface

- The web app is now a single-page application (Vite + PrimeVue + Vue Router
  + Pinia), faster and more responsive than the old template-based UI.
- Sortable observations table, redesigned area cards, and advanced filters in
  modals.
- Switch between scientific and vernacular species names everywhere, from a
  navbar toggle. Vernacular names now also appear in the map popup (#165).

## New filtering

- Filter observations by proximity to your areas: inside, approaching, or both,
  with a configurable distance (default 5 km) (#300).

## A new public API (v2)

- Modern REST API under `/api/v2` (Django Ninja) with an OpenAPI schema and a
  self-service `/api-docs` hub.
- Personal API tokens, created and revoked from `/api-tokens`, with Bearer-token
  auth on write endpoints and rate limiting.
- The legacy `/api/*` endpoints are deprecated and carry a published Sunset date.

## A new Docker and deployment setup

- Images are now published to GHCR (`ghcr.io/riparias/gbif-alert`); Docker Hub
  is no longer maintained.
- Configuration is driven by environment variables (`.env` / `DATABASE_URL`),
  replacing the old bind-mounted Python settings file.
- Static files are served by WhiteNoise - the bundled nginx image is gone; bring
  your own reverse proxy for TLS and routing.
- Rewritten compose stack on a single network: Valkey (replacing Redis), a
  one-shot `migrate` service, an ofelia scheduler for imports/notifications, an
  opt-in `bundled-db` profile, and a `/healthz` liveness endpoint. A bare
  `docker compose up` works with no host prerequisites.
- Dokploy: a dedicated `docker-compose.dokploy.yml` (single file, every service
  on the external `dokploy-network`); on recent Dokploy the Domains tab routes
  the service automatically (no manual Traefik config). See `INSTALL.md`.

## Under the hood

- Django 5.2 LTS (from 4.2), Python 3.13, psycopg3.
- Dependency management migrated from Poetry to uv.
- Large refactor of the observation-import pipeline with a substantially
  expanded test suite, plus assorted internal cleanup.

## Breaking changes (for operators upgrading)

- **Image registry**: update `image:` references from `niconoe/gbif-alert` to
  `ghcr.io/riparias/gbif-alert`.
- **Configuration**: settings are now env-var driven with an optional
  `local_settings.py` escape hatch; the `local_settings_docker.py` bind-mount
  pattern is gone. See `INSTALL.md` and `.env.example`.
- **Reverse proxy required**: the custom nginx image and `static_volume` are
  removed; provide your own proxy (Dokploy/Traefik, ALB, ...) for TLS.
- **Redis -> Valkey**: the compose broker service is renamed `redis` -> `valkey`
  (drop-in, same RESP protocol).
- **Bundled Postgres 15 -> 17**: the `bundled-db` profile now uses
  `postgis/postgis:17-3.5`; existing bundled-db deployments need a `pg_upgrade`
  or dump/restore. Managed/external Postgres is unaffected.

# 1.9.0 (2026-03-06)

- Allow to filter observations per basis of record
- By default, (at page load), only unseen observations are shown
- Allow to filter observations per validation status
- Multiple user interface improvements (https://github.com/riparias/gbif-alert/issues/145, https://github.com/riparias/gbif-alert/issues/296, https://github.com/riparias/gbif-alert/issues/290, ...)
- Updated backend and frontend dependencies
- Multiple internal improvements (https://github.com/riparias/gbif-alert/issues/282, ...)

# 1.8.0 (2026-02-04)

- Observations are automatically marked as seen after a configurable delay (default: 1 year). Users can configure this delay in their profile settings.
- When creating a new alert, existing observations matching the alert criteria are automatically marked as seen (to avoid overwhelming users with old data).
- Major refactor of the seen/unseen mechanism and import process to improve performances.
- Other internal improvements and code clean-up.

# 1.7.8 (2025-03-13)

- Adjusted the import process for a recent GBIF API metadata change

# v1.7.7 (2024-11-07)

- Fixed a bug with the maps API (see https://github.com/riparias/gbif-alert/issues/283)

# v1.7.6 (2024-07-26)

- Another map performance improvement (missing index)

# v1.7.5 (2024-07-25)

- Fix a compatibility issue with Windows platform (data import script). Thanks, @sronveaux!
- Major improvements under the hood to map performances (Thanks for the suggestion, @sronveaux and @silenius!)

# v1.7.4 (2024-05-24)

- Technical: updated all backend dependencies
- Technical: updated the frontend dependencies
- API: added a new "short" mode for the observations (table) API endpoint
- moved some endpoints from the internal to the public API (to reflect external usage)

# v1.7.3 (2024-03-26)

- Fixed two bugs related to the maintenance mode: https://github.com/riparias/gbif-alert/issues/277 and https://github.com/riparias/gbif-alert/issues/278

# v1.7.2 (2024-03-25)

- WFS server: the (internal) species_id field is now available

# v1.7.1 (2024-03-25)

- Improvements to the WFS server, following user feedback (https://github.com/riparias/gbif-alert/issues/268)
- Fixed bug with map background (https://github.com/riparias/gbif-alert/issues/276)
- Technical: got rid of webdriver-manager, now using the manager provided by selenium itself
- Technical: updated all backend dependencies
- Technical: updated the frontend dependencies

# v1.7.0 (2023-11-08)

- Improvements to the WFS server (https://github.com/riparias/gbif-alert/issues/268)
- Robustness: removed the field size limitation for the dataset name (was 255 chars)
- Updated backend dependencies
- New data import scripts (specific to the LIFE RIPARIAS instance)

# v1.6.1 (2023-10-02)

- Fix typo in Dutch translation

# v1.6.0 (2023-09-29)

- Major: The application is now available in Dutch
- More automated tests to improve robustness (https://github.com/riparias/gbif-alert/issues/93, https://github.com/riparias/gbif-alert/issues/131)
- Remove deprecated settings (https://github.com/riparias/gbif-alert/issues/265)
- Fix an old and annoying bug for administrators: https://github.com/riparias/gbif-alert/issues/146
- New data import script (specific to the LIFE RIPARIAS instance)

# v1.5.0 (2023-09-26) 

- Major: Users can now upload their owns areas of interest!
- Fixed an old display/linking bug (https://github.com/riparias/gbif-alert/issues/244)
- Vernacular name of species is now shown on the occurrence details page (https://github.com/riparias/gbif-alert/issues/262)
- Scientific name of species is now shown on the map popup (https://github.com/riparias/gbif-alert/issues/263)
- Improved test coverage for more robustness
- New data import script (specific to the LIFE RIPARIAS instance)
- Improvements to the table sorting mechanism (https://github.com/riparias/gbif-alert/issues/130)

# v1.4.1 (2023-09-18)   

- New data import script (specific to the LIFE RIPARIAS instance)

# v1.4.0 (2023-09-13)

- Experimental: a WFS server (returning all observations) is now available at `/api/wfs/observations`
- The histogram / bar chart now shows the full temporal range of data (instead of the last 5 years)
- Improved import script again to avoid crashes due to high memory usage

# v1.3.2 (2023-09-12)

- Improve import performances

# v1.3.1 (2023-09-07)

- Warning message instead of histogram when all values are 0, to avoid confusing display behaviour: https://github.com/riparias/gbif-alert/issues/92
- Fix a minor, recently introduced display issue: https://github.com/riparias/gbif-alert/issues/255
- Unused datasets are automatically cleaned up at import time: https://github.com/riparias/gbif-alert/issues/222
- Better synchronization of the Dataset name with GBIF: https://github.com/riparias/gbif-alert/issues/183
- More user-friendly language settings (https://github.com/riparias/gbif-alert/issues/257)

# v1.3.0 (2023-08-30)

- Users can now easily change their password
- The vernacular name is now shown in the observations table
- Improved "initial data import" filter/selector, according to the suggestions in https://github.com/riparias/gbif-alert/issues/251
- Internal improvement to improve the tool re-usability (https://github.com/riparias/gbif-alert/issues/250)
- Update dependencies

# v1.2.1 (2023-08-21)

- Fixed a display issue with the user menu in the navbar (https://github.com/riparias/gbif-alert/issues/252)

# v1.2.0  (2023-07-31)

- The GBIF download is now fully configurable, so instances are not limited to a single country
and can use any search predicate (see https://www.gbif.org/developer/occurrence#predicates)
- Improved installation instructions, including the template for the `local_settings_docker.py` file
- Added python-dotenv to the requirements so settings secrets can be configured via .env files

# v1.1.2  (2023-07-25)

- Minor changes to the Docker Compose setup

# v1.1.1  (2023-07-24)

- Minor changes to the Docker Compose setup

# v1.1.0  (2023-07-20)

- The project was renamed from `pterois` to `gbif-alert`
- Infrastructure: we now provide a Docker / Docker Compose setup for easier deployment
- Minor: A proper git tag name is shown as the version number in footer (if available, otherwise the commit hash is used as it was before)
- Minor: Better response if a user tries to see the details of someone else's alert (https://github.com/riparias/gbif-alert/issues/223)


# v1.0.0  (2023-07-12)

- First release as a reusable engine
