# Unreleased

- Fix: an alert selecting several hundred species no longer breaks the page it
  is viewed on. The filters were sent as one web address parameter per species,
  which overflowed the web server's limit on address length; they are now sent
  in a compact form. Existing links and bookmarks keep working.
- Fix: the password reset screens no longer show a "404 - Page not found"
  message above the form. The four pages of the flow (request, instructions
  sent, set a new password, and confirmation) are rendered by Django rather
  than by the single-page app, and the app mistook them for unknown addresses.

# 2.5.1 (2026-08-27)

- Feature: the site is now usable on a phone. The navigation bar collapses into
  a menu instead of running off the screen, the filter and alert panels move
  into a slide-out drawer, and the observation table becomes a list of tappable
  cards. On a small screen an alert opens on that list rather than on the map,
  with the seen/unseen filter and "mark all as viewed" kept within reach.
- Fix: datasets no longer appear with an empty name in the dataset filter. GBIF
  downloads rarely carry a dataset name, so it is now taken from the GBIF
  registry instead, at the end of every import. A dataset that already has a
  name keeps it, even if GBIF is unreachable.
- Feature: the new `sync_dataset_names` management command names the datasets of
  an existing instance right away, without waiting for the next import.

# 2.5.0 (2026-08-26)

- Feature: operators can now update an existing species through the API, with
  `PATCH /api/v2/species/{id}/`. Any subset of the fields can be sent - tags,
  scientific name, vernacular names, taxon keys or image details - and what is
  not sent is left alone. Sending `tags` replaces the species' whole tag list.
- Change: filtering observations by area is much faster. On a database of a
  million observations, an alert covering 62 areas went from 16 seconds to under
  one, and one covering 12 areas from 4 seconds to a few milliseconds. Maps,
  lists and notification emails all benefit. The exception is an alert whose
  areas cover nearly every observation in the database, which gets somewhat
  slower.
- Fix: selecting several areas at once no longer fails when one of them has a
  self-intersecting boundary. Such a combination previously returned a server
  error, on both the map and the observation list.
- Change: an observation lying exactly on the boundary of an area now counts as
  inside it, on maps, lists and alerts alike. Previously it was excluded. No
  observation in the LIFE RIPARIAS database was affected by this.
- Feature: an area can now be pre-selected as the home page's default filter.
  Tick "Is default home filter" on a public area in the admin, and visitors
  land on a home page already scoped to it - useful when the instance
  downloads a wider region than it focuses on. The filter can be removed like
  any other one.
- Feature: instances funded by the European Union can now show the official
  "Funded by the European Union" emblem in their footer, linking to their "about
  this site" page. It is off by default and enabled with the new
  `SHOW_EU_FUNDING_ACKNOWLEDGEMENT` setting; see
  `docs/eu-funding-acknowledgement.md` for what an EU-funded instance must
  display and where.

# 2.4.0 (2026-08-17)

- Change: importing observations is about 2.75x faster. On a test database
  holding a million observations with real users and alerts, a full re-import
  went from roughly 72 minutes to 26 minutes. Two things account for it:
  reading the GBIF archive is about 12x faster, and deciding whether an
  observation is already known now takes one database query per batch of
  10,000 instead of five per observation - the second is by far the larger
  share.
- Feature: a new "Species" tab in the results view lists the species present in
  the current search along with their observation counts and shares. The
  species count in the sidebar now links to it.
- Change: the observations list, the date filter, the "not viewed" filter and
  the histogram are now served by database indexes rather than sorting or
  scanning the whole dataset on each request - the histogram was about 4x
  faster in testing. The import leaves the database ready for them, too.
- Change: on the "About the data" page, older data imports can now be expanded
  to show the same details as the most recent one - date range, imported, new
  and skipped observation counts, and the GBIF download link. Previously only
  their one-line summary was available.
- Change: the observations map now grows to fill the page down to the footer
  instead of staying at a fixed height, which left a large empty band below it
  on a tall screen. It never gets shorter than it used to be, so smaller
  screens are unaffected.

# 2.3.0 (2026-07-23)

- Fix: clicking a navigation link right after another one could be silently
  ignored, leaving you on the page you were trying to leave with a stray
  `?status=all` appended. The index page's filter sync outlived the page
  itself and overrode the navigation you had just asked for.
- Change (operator-facing): importing species from a CSV/XLSX file in the admin
  now validates each row, instead of storing whatever it is given. A row with
  no taxon key at all - which would block the next observation import - is
  rejected, as are malformed image URLs and over-long names. Exporting,
  editing and re-importing the app's own data is unaffected.
- Feature: a species can now be added with only a Catalogue of Life (COL XR)
  taxon key. The GBIF backbone key is frozen, so a species described after the
  freeze has none - until now that made it impossible to monitor. At least one
  of the two keys is still required.
- Change: the WFS observations endpoint gained a `species_col_key` element,
  alongside the existing `species_gbif_key`. Existing consumers are unaffected;
  the new element is the one to prefer, since `species_gbif_key` is empty for a
  species that only has a COL key.
- Change (API v2): `gbifTaxonKey` can now be null in species responses, and is
  optional when creating a species.
- Feature: operators can now create, rename and delete shared areas - visible to
  every user - through the API, instead of editing and re-running the
  `load_area` command. Areas can also carry tags, and a name can no longer be
  used twice by the same owner.
- Change (breaking, API v2): creating an area from GeoJSON is now
  `POST /api/v2/areas/`; uploading an area file moved to
  `POST /api/v2/areas/from-file/`. The GeoJSON endpoint also accepts a single
  Feature or a bare Polygon / MultiPolygon geometry now, not only a
  FeatureCollection.
- Fix: selecting an area now draws its boundary on the map, above the hexagons
  and points. The outline was never displayed at all - observations were
  filtered by the area, but nothing showed where it was.
- Change: the main navigation is more compact - "About this site" and "About the
  data" are grouped under an "About" menu, "Explore all observations" is now
  "Explore", and the language selector shows only the language code.
- Fix: the "What's new" and "My alerts" notification dots no longer stay lit
  after you visit the page; they now clear without a full page reload.
- Fix: several settings were silently ignored under Docker/Dokploy because the
  compose files never passed them to the containers - most visibly the GBIF
  download bounding box, plus the log level, email/SES options, CSRF trusted
  origins and API throttle rates. Redeploy to pick up any you have set.
- Feature: observations are now downloaded and matched against the Catalogue of
  Life Extended Release (COL XR), the taxonomy GBIF adopted after freezing its
  own backbone. This keeps the app in step with current taxonomy and also finds
  records the frozen backbone was dropping, such as the hybrids *Reynoutria* x
  *bohemica* and *Spiraea* x *billardii*.
- Upgrade (operator action required): run `python manage.py migrate`, then
  `python manage.py convert_taxon_keys_to_col`. Species it cannot resolve are
  reported instead of guessed - curate those in the admin. A custom
  `PREDICATE_BUILDER` in `local_settings.py` must be updated to use
  `gbif_col_taxon_key` and the COL `checklistKey`. `import_observations` refuses
  to run until every species has a COL key. See INSTALL.md.
- Feature: the species filter shows the COL taxon key, linked to gbif.org. The
  public `/species/` API also exposes `gbifColTaxonKey`; `gbifTaxonKey` is
  unchanged, so the change is additive for API consumers.
- Dev/infra: the frontend now has a prettier config (4-space indent, 100
  columns) and has been formatted with it. Use `npm run format`; CI checks it.
- Dev/infra: the Python codebase is now black-formatted throughout, and CI
  checks it - the counterpart to the prettier check above, whose absence is why
  29 files had drifted.

# 2.2.1 (2026-07-13)

- Diagnostics: the observation import now logs peak RSS (memory high-water mark)
  on every step and flushes each log line immediately, so an out-of-memory kill
  can no longer swallow the lines that point at the crashing step. It also
  brackets the DwCA metadata read (whose line-offset index scales with the row
  count) and logs the GBIF predicate sent to the download API together with the
  download API's response (download id, retries, non-200 statuses). This is
  instrumentation only - no change to import behavior - added to locate an
  out-of-memory crash on large first imports.

# 2.2.0 (2026-07-10)

- Feature: the GBIF download can be scoped to a lat/lon bounding box via env
  vars (`GBIF_DOWNLOAD_LAT_MIN` / `LAT_MAX` / `LON_MIN` / `LON_MAX`), the same
  way `GBIF_DOWNLOAD_COUNTRY` and `GBIF_DOWNLOAD_YEAR_MIN` already scope by
  country and year - no custom `PREDICATE_BUILDER` needed. Set all four or none;
  a partial or out-of-range box fails fast at startup.

# 2.1.0 (2026-07-10)

- Feature: operators can create species through the public API
  (`POST /api/v2/species/`, superuser only), so species can be added by script
  instead of only via the admin. Accepts the same fields as the admin form
  (scientific name, GBIF taxon key, per-language vernacular names, tags, image
  fields) and works with a personal access token or a session.
- Feature: operators can publish reusable "alert templates" - shared,
  pre-configured filter presets that users copy into their own alerts.

# 2.0.8 (2026-07-08)

- Fix: signing out from the navbar user menu returned a 405 error instead of
  logging the user out. Sign-out was a plain GET link to Django's `LogoutView`,
  which rejects everything but POST since Django 5. It now posts to a dedicated
  `POST /api/v2/auth/signout/` endpoint (matching the rest of the SPA auth flow)
  and redirects home. The unused legacy `accounts/signout/` route and its nav
  config plumbing were removed.

# 2.0.7 (2026-06-26)

- Dev/infra: clones and CI no longer download the 209 MB Belgian-municipalities
  LFS file by default (`.lfsconfig` `fetchexclude`), which was burning GitHub LFS
  bandwidth on deploy. The file is instance-specific and already loaded on the
  RIPARIAS database; fetch it on demand with
  `git lfs pull --include=source_data/public_areas/belgian_municipalities/adminvector_4326.gpkg --exclude=`.
- Fix: switching pages from the main navigation menu no longer triggers a
  full-page reload (a visible "blink"/flash). The navbar links pointed at routes
  that the Vue SPA already handles, but rendered them as plain anchors, so every
  click did a Django round-trip that re-bootstrapped the entire app. Ordinary
  left-clicks on internal links now navigate client-side via Vue Router, while
  genuinely external Django routes (admin, sign-out) and modifier/middle clicks
  still do a real navigation.
- Feature: species can now have an optional representative picture, referenced by
  URL (no media files stored). Editable in the admin, with a `populate_species_images`
  management command that auto-fills from Wikipedia/Wikimedia (GBIF occurrence media
  as fallback) and never overwrites manually curated images. The picture and its
  credit are shown in the species-name hover tooltip, and the image fields are
  exposed on the public `/species/` API.

# 2.0.6 (2026-06-23)

- Fix: `import_observations` could be OOM-killed (exit 137) during the "migrating
  unseen observations" step on instances with a large number of unseen
  observations. `migrate_unseen_observations()` loaded every `ObservationUnseen`
  row into memory with fully-hydrated related objects (each `Observation` carries
  a geometry and several text fields), rebuilding the same observation once per
  user it was unseen for. It now streams the rows and fetches only the scalar
  columns the logic needs, keeping peak memory bounded. Behavior is unchanged.
  Per-step peak-RSS logging was added so the memory profile can be measured.

# 2.0.5 (2026-06-23)

- Fix: an `import_observations` run interrupted mid-flight (e.g. a redeploy that
  SIGKILLs the import) no longer strands the site in maintenance mode. The import
  enables maintenance for its whole duration and previously relied on a `finally`
  to clear it, which does not run on SIGKILL. The import now tags its maintenance
  with a marker, and the web container clears import-set maintenance on startup -
  self-healing even on a hard kill - while leaving a manually enabled maintenance
  window untouched (#362).

# 2.0.4 (2026-06-22)

- Fix: running more than one gbif-alert stack on a single Docker host (sharing
  `dokploy-network`) no longer cross-contaminates them. Each stack defines a service
  named `valkey`, and on a shared network Docker resolves the bare name to every
  stack's Valkey at random, mixing the Django cache, the RQ job queue, and
  maintenance-mode state across sites - the visible symptom being intermittent
  maintenance-mode 503s on one site while another was importing. A new optional
  `VALKEY_HOST` variable (default `valkey`) now drives both the Redis URL and the
  Valkey network alias, so each deployment talks only to its own Valkey. Set it to a
  unique value per co-located stack; a single-stack host needs no change (#361).

# 2.0.3 (2026-06-22)

- New: optional Amazon SES email backend. Set `EMAIL_BACKEND=django_ses.SESBackend`
  and `AWS_SES_REGION_NAME` to send notification and admin error mail through SES
  using the ambient AWS credentials (an ECS task / EC2 instance IAM role - no SMTP
  user, password, or access keys stored). The default stays SMTP and is unchanged;
  the new SES settings are inert unless that backend is explicitly selected.
  `DEFAULT_FROM_EMAIL` must be a verified SES identity (#360).

- Fix: a malformed `ADMINS` environment variable now fails fast at startup with a
  clear error naming the offending entry, instead of being silently kept as a
  garbage address that only crashed days later inside `mail_admins()` during a
  data import. `ADMINS` is an env-var string ("Name <a@b>, Name2 <c@d>"), not a
  Python list literal, and is now validated as such (#358).

- Fix: a failing observation import no longer strands the site in maintenance
  mode. Maintenance is now always cleared (safe, because the import runs in a
  single transaction that rolls back on failure), and admins are emailed the
  exception traceback before the job exits non-zero - previously a crashing
  import left maintenance ON and sent no notification (#359).

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
