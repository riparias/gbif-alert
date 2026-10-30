# Deploy a GBIF Alert instance

Deploying a GBIF Alert instance allows you to target a specific community of users by:
- Defining the taxonomic, temporal and spatial scope of the alert tool.
- Customize the website content.

## Customizable parts

You can customize:

- The subset of [GBIF occurrences](https://www.gbif.org/occurrence/) to monitor, e.g.
only [occurrences of the 5 invasive alien fishes in New Zealand](https://www.gbif.org/occurrence/search?country=NZ&taxon_key=2367196&taxon_key=2350580&taxon_key=2362635&taxon_key=2340989&taxon_key=8215487). Those are the **only** occurrences that GBIF Alert 
will periodically download from GBIF and will import in its database.
- Your end-users will be able to filter those occurrences further to match their specific needs.
- The available languages in the interface: English, French, Dutch and Norwegian Bokmal are currently supported.
- Website texts: the introduction on the home page, the "about this site" page and the "what's new" page.
- Whether the footer carries the EU funding acknowledgement, via `SHOW_EU_FUNDING_ACKNOWLEDGEMENT` (off by default, and reserved for genuinely EU-funded instances - see [docs/eu-funding-acknowledgement.md](docs/eu-funding-acknowledgement.md)).
- The primary color theme of the interface, via the `PRIMEVUE_PRIMARY_PALETTE`
  setting (e.g. `indigo`, `emerald`, `blue`, `rose`; see `.env.example`).

## Dependencies

Technically speaking, GBIF Alert is a [Django](https://www.djangoproject.com/)-based website, with the following dependencies:

- [Python](https://www.python.org/)
- [PostgreSQL](https://www.postgresql.org/) with [PostGIS](https://postgis.net/)
- [Valkey](https://valkey.io/) (or [Redis](https://redis.io/))
- [NPM](https://www.npmjs.com/) (for frontend assets)

(see [CONTRIBUTING.md](CONTRIBUTING.md) for specific versions and more details on the inner working of the tool).

While a manual installation of those components is possible, we recommend using [Docker Compose](https://docs.docker.com/get-started/08_using_compose/) to install and run GBIF Alert. 
It will make your life much easier!

Please note that in order to run a production GBIF Alert instance, you will need to have access to the following resources:

- A server running Linux with a public IP address, a domain name and a TLS certificate (the site must be served over HTTPS, see *HTTPS is required* below)
- Access to an [SMTP server](https://en.wikipedia.org/wiki/Simple_Mail_Transfer_Protocol) (for sending notification emails)
- A [GBIF account](https://www.gbif.org/user/profile) dedicated to the instance (the import requests GBIF downloads with it)

## Install and run GBIF Alert through Docker Compose

The Docker Compose stack is production-only. For local development, use the manual install (see below).

### Prerequisites

- Docker (Engine 24+) and Docker Compose v2.20 or newer.
- A Postgres + PostGIS database. You can either:
  - **Bring your own** (recommended for production: managed Postgres on Dokploy, RDS, etc.). PostGIS extension required.
  - **Use the bundled `db` service** (good for testing or hobbyist self-hosting). Backups are your responsibility.
- An external reverse proxy in front of the stack (Dokploy/Traefik, ALB, Nginx, ...) handling TLS and routing. The `gbif-alert` container exposes port 8000 and serves static files via WhiteNoise; no nginx in compose. The compose file ships **no routing or TLS config of its own** - you wire the proxy to the app yourself (see *Reverse proxy, TLS, and multiple instances* below).

### Initial deploy

1. Create a directory for the deploy:
   ```
   mkdir gbif-alert-deploy && cd gbif-alert-deploy
   ```

2. Download the two artefacts from the release tag (replace `v2.11.0` with the version you want; see the [releases](https://github.com/riparias/gbif-alert/releases)):
   ```
   curl -O https://raw.githubusercontent.com/riparias/gbif-alert/v2.11.0/docker-compose.yml
   curl -O https://raw.githubusercontent.com/riparias/gbif-alert/v2.11.0/.env.example
   ```

3. Copy the env template and edit:
   ```
   cp .env.example .env
   $EDITOR .env
   ```

   Set at minimum: `SECRET_KEY`, `DATABASE_URL`, `SITE_BASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_NAME`, and `GBIF_ALERT_TAG` (the image tag to pull - e.g. `devel` or a release like `2.11.0`, without the `v`; required, no default). See `.env.example` for the full contract. The Docker stack is **entirely env-driven** - you do not need a `local_settings.py`. (For a Python-only override like a custom `PREDICATE_BUILDER`, see the Custom predicate note below.)

4. Bring up the stack:
   - With external Postgres:
     ```
     docker compose up -d
     ```
   - With the bundled Postgres+PostGIS (set `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` in `.env` first):
     ```
     docker compose --profile bundled-db up -d
     ```

5. Confirm the stack came up cleanly before continuing:
   ```
   docker compose ps            # wait until `gbif-alert` shows "healthy" (~30s)
   docker compose logs gbif-alert   # check for a clean gunicorn startup
   ```
   The `gbif-alert` container has a `/healthz` healthcheck; if it never reaches
   "healthy", the logs will show why (usually a bad `DATABASE_URL` or a missing
   required env var).

6. Create the first superuser:
   ```
   docker compose exec gbif-alert python manage.py createsuperuser
   ```

7. Visit your site (via the reverse proxy you set up in front of port 8000) and log in to the admin (`/admin`).

8. Set up the content before the first import. A fresh instance has no species and no observations:
   - **Species** (Dashboard > Species): add every taxon to monitor, with its Catalogue of Life Extended Release (COL XR) taxon key - the alphanumeric key in the taxon's gbif.org address (`https://www.gbif.org/taxon/<key>`, e.g. `C5KM`). The legacy numeric GBIF backbone key is optional. The admin also imports a CSV/XLSX list. `import_observations` refuses to run while a species has no COL XR key.
   - **Texts** (Page fragments): create three fragments, Markdown with one text per language, under the identifiers `welcome_text` (home page introduction), `about_this_site_page_content` and `news_page_content` ("what's new"). A missing fragment shows nothing, so the site works before you write them.
   - **Areas** (Dashboard > Areas, optional): public areas users can filter on. Draw them in the admin, or load a file with `load_area` (see CONTRIBUTING.md).
   - **First import**: run it by hand once rather than waiting for the nightly schedule, so a wrong download filter or GBIF credentials show up now:
     ```
     docker compose exec gbif-alert python manage.py import_observations
     ```
     A GBIF download takes minutes to hours to prepare. While the import loads the data, the site shows a maintenance page (see *Periodic tasks* below).

### HTTPS is required

With `DEBUG=False` the app hardens itself for HTTPS: session and CSRF cookies are
marked `Secure`, plain HTTP requests are redirected to HTTPS and an HSTS header
is sent. The app learns the original scheme from the `X-Forwarded-Proto` header,
so the reverse proxy **must** terminate TLS and send `X-Forwarded-Proto: https`
(Traefik and Caddy do by default; for Nginx see *Plain Nginx / Caddy / ALB*
below). A proxy that does not send it, or an instance served over plain HTTP,
ends in a redirect loop.

The hardening knobs (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE`, `SECURE_HSTS_*`, documented in `.env.example`) are **not**
forwarded by the compose files - the Docker stack always runs with the production
defaults. They can only be changed on a manual deploy. Plain-HTTP operation is
therefore limited to local development (`DEBUG=True`).

### Reverse proxy, TLS, and multiple instances

The stack ships **no routing or TLS config** - that is the operator's job, and how you wire it depends on your platform. The app listens on container port 8000; expose it one of two ways:

- **Published host port** (most portable): `GBIF_ALERT_BIND` publishes the app on the host (default `127.0.0.1:8000`). Point a host-level proxy (Nginx, Caddy) at that address for TLS and routing.
- **Docker network** (Dokploy, self-managed Traefik): the proxy reaches the `gbif-alert` container over a shared Docker network on port 8000. The `GBIF_ALERT_BIND` host port is then unused for routing, but the compose still publishes it - keep it unique on a shared host (see below).

Per platform:

- **Dokploy (Compose stacks)**: recent Dokploy with an up-to-date Traefik routes
  Compose services automatically. Set the domain in the service's **Domains** tab
  (enable Let's Encrypt, point it at container port `8000`); Dokploy injects the
  Traefik labels (`traefik.enable`, `Host()` routers, `web`+`websecure`
  entrypoints) into the deployed compose and attaches the container to
  `dokploy-network`. No manual file-provider config is needed. Two things to get
  right, or Traefik returns a **404** (it drops the router for any unhealthy
  container):
  - The container must be **healthy** - so put the domain *and* `localhost` in
    `DJANGO_ALLOWED_HOSTS` (the `/healthz` check hits `localhost`), and the domain
    in `DJANGO_CSRF_TRUSTED_ORIGINS`.
  - The app and what it talks to (Traefik, a managed Postgres) must share
    `dokploy-network`. `docker-compose.dokploy.yml` puts every service there and
    nowhere else, which avoids this; intermittent `Temporary failure in name
    resolution` is the symptom of a container multi-homed on `dokploy-network`
    *and* a compose bridge at once - pin it to `dokploy-network` only.
- **Self-managed Traefik, or older Dokploy that does not inject labels**: add
  Traefik labels to the `gbif-alert` service, or hand-write a file-provider
  config (legacy example below). Use router/service names unique per instance.
- **Plain Nginx / Caddy / ALB**: front the published `GBIF_ALERT_BIND` address
  with your proxy config for TLS and routing. Nginx does not forward the scheme
  on its own; the `location` block needs at least:
  ```nginx
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  ```
  Caddy's `reverse_proxy` and an ALB set these headers by default.

**Proxy count (`NINJA_NUM_PROXIES`)**: the API rate limits, including the
sign-in limit that slows down password guessing, identify clients by the IP in
`X-Forwarded-For`. Set `NINJA_NUM_PROXIES` to the number of proxies in front of
the app: the default `1` fits a single Traefik/Nginx/Caddy; use `2` behind a CDN
or load balancer plus a proxy, and `0` if nothing is in front. A value that is
too high lets clients forge their IP and bypass the limits; one that is too low
makes all visitors share a single limit.

**Running several instances on one host**: each needs its own domain and a
**unique** `GBIF_ALERT_BIND` host port (e.g. `127.0.0.1:8001`, `127.0.0.1:8002`).
A host port can only be bound by one container; reusing `127.0.0.1:8000` fails
with `port is already allocated`. Routing reaches the container over the Docker
network, so this bind only needs to avoid the clash.

**Legacy fallback - manual Traefik file-provider config** (only if your Traefik
does *not* inject labels for Compose services, e.g. older Dokploy). Dokploy's
Traefik watches `/etc/dokploy/traefik/dynamic/`; drop one file there per instance
with unique router/service names:

```yaml
# /etc/dokploy/traefik/dynamic/gbif-alert-myinstance.yml
http:
  routers:
    gbif-alert-myinstance-web:
      rule: Host(`alerts.example.org`)
      service: gbif-alert-myinstance
      middlewares: [redirect-to-https]   # Dokploy ships this middleware; omit it elsewhere
      entryPoints: [web]
    gbif-alert-myinstance-websecure:
      rule: Host(`alerts.example.org`)
      service: gbif-alert-myinstance
      entryPoints: [websecure]
      tls:
        certResolver: letsencrypt
  services:
    gbif-alert-myinstance:
      loadBalancer:
        servers:
          - url: http://<container-name>:8000
        passHostHeader: true
```

Point `url:` at the `gbif-alert` container's full name on `dokploy-network`
(`docker ps --format '{{.Names}}' | grep -- '-gbif-alert-'`). Traefik hot-reloads
the file; update `url:` if you recreate the project (the container name's hash
changes). A bare `404 page not found` means no matching router loaded (file not
loaded / mangled `Host()` rule).

### Dokploy

Dokploy is one supported target, but nothing in the base stack assumes it.
Dokploy's Compose Path field takes a **single** file (it cannot apply a second
`-f` overlay), so deploy with the dedicated **`docker-compose.dokploy.yml`**: in
the Compose service, set the **Compose Path** to that file. It includes the full
stack and puts every service single-homed on the external `dokploy-network`.

- **Routing**: in the **Domains** tab, add your domain with **Service Name
  `gbif-alert`** and **port `8000`** (enable Let's Encrypt). Dokploy then injects
  the Traefik labels automatically - no manual config. The Service Name must be
  exactly the compose service (`gbif-alert`); a blank or wrong one leaves the
  service unrouted (a 404 with healthy containers). See the Dokploy notes under
  *Reverse proxy, TLS, and multiple instances* above for the other 404 gotchas
  (`DJANGO_ALLOWED_HOSTS` must include the domain *and* `localhost`).
- **Database**: use a managed/external Postgres via `DATABASE_URL` (do not enable
  the bundled-db profile on Dokploy). Because `docker-compose.dokploy.yml` puts
  *all* services - including `migrate` and `rqworker`, which Dokploy does **not**
  auto-attach (only the domain'd web service is) - on `dokploy-network`, they can
  reach a Dokploy-managed Postgres (a sibling container on that network) by name.
  A Postgres reachable by host:port works too.
- **`GBIF_ALERT_BIND` is unused on Dokploy** - this file publishes no host port;
  Traefik routes to container port 8000 over `dokploy-network`. Don't set it (it
  only affects the host-published port in the base `docker-compose.yml`).

### Customising your instance

All operationally-significant settings live in `.env`. Highlights:

- **Branding**: `SITE_NAME`, `PRIMEVUE_PRIMARY_PALETTE`.
- **Web workers**: `GUNICORN_WORKERS` (default `3`) is the number of gunicorn worker processes in the `gbif-alert` container. The usual rule is two per CPU core plus one.
- **Map default view**: `MAP_INITIAL_ZOOM`, `MAP_INITIAL_LAT`, `MAP_INITIAL_LON`.
- **Languages**: `ENABLED_LANGUAGES` (comma-separated subset of `en,fr,nl,nb`;
  `nb` is Norwegian Bokmal).
- **EU funding acknowledgement**: `SHOW_EU_FUNDING_ACKNOWLEDGEMENT` (default `False`). When `True`, every page shows the official "Funded by the European Union" emblem in the footer, linking to your "about this site" page. **Only switch this on if your instance is genuinely funded by the European Union** - displaying the emblem otherwise is a false claim of EU support. Such an instance must also put the full disclaimer on its "about this site" page: see [docs/eu-funding-acknowledgement.md](docs/eu-funding-acknowledgement.md) for ready-to-paste text.
- **Verified status per dataset**: an observation is normally flagged as verified based on its `identificationVerificationStatus`. `ALWAYS_VERIFIED_DATASET_KEYS` and `NEVER_VERIFIED_DATASET_KEYS` (comma-separated GBIF dataset keys) bypass that check for whole datasets. `ALWAYS_VERIFIED_DATASET_KEYS` defaults to the iNaturalist research-grade dataset (`50c9509d-22c7-4a22-a47d-8c48425ef4a7`), whose records reach GBIF without a verification status; note that research grade means community consensus, not expert validation, so set the variable to an empty value if that is not good enough for your instance. Changes apply at the next observation import.
- **Email**: SMTP by default (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`). To send through **Amazon SES with an IAM role** instead of SMTP credentials, set `EMAIL_BACKEND=django_ses.SESBackend` and `AWS_SES_REGION_NAME` (e.g. `eu-west-1`); the credentials are then taken from the ambient AWS role (ECS task role / EC2 instance role), so no SMTP user/password is stored. `DEFAULT_FROM_EMAIL` must be a verified SES identity.
- **Co-hosting multiple stacks on one host**: if you run more than one gbif-alert deployment on the same Docker host sharing `dokploy-network`, set `VALKEY_HOST` to a unique value per deployment (e.g. `VALKEY_HOST=mysite-valkey`). Each stack defines a service named `valkey`, and on a shared network the bare name resolves to every stack's Valkey at random - cross-contaminating the cache, the RQ queue, and maintenance-mode state. A unique `VALKEY_HOST` points each app at its own Valkey. A single-stack host needs no change (it defaults to `valkey`).
- **GBIF download filter**: `GBIF_DOWNLOAD_USERNAME`, `GBIF_DOWNLOAD_PASSWORD`, `GBIF_DOWNLOAD_COUNTRY`, `GBIF_DOWNLOAD_YEAR_MIN`, an optional `GBIF_DOWNLOAD_CONTINENT` (e.g. `EUROPE`; GBIF's coordinate-derived continent), and an optional lat/lon bounding box `GBIF_DOWNLOAD_LAT_MIN` / `GBIF_DOWNLOAD_LAT_MAX` / `GBIF_DOWNLOAD_LON_MIN` / `GBIF_DOWNLOAD_LON_MAX` (set all four or none; degrees, WGS84), and an optional polygon `GBIF_DOWNLOAD_GEOMETRY` (a WKT Polygon or MultiPolygon in WGS84 lon/lat, pasted on one line; exterior rings anticlockwise and holes clockwise, as GBIF reads a clockwise exterior ring as "everything outside it"; a malformed or wrongly wound polygon stops the deploy at the `migrate` step). The default predicate builder uses these to construct the download filter; all filters AND together (a continent-wide instance leaves `GBIF_DOWNLOAD_COUNTRY` empty). Species are matched through the COL XR checklist `GBIF_COL_XR_CHECKLIST_KEY`; it defaults to the current COL XR dataset key and only needs changing if GBIF publishes a new one.
- **Default home page area filter** (Django admin, not `.env`): tick "Is default home filter" on a public area (Dashboard > Areas) to have the home page open with that area pre-selected in its filters. Visitors can remove it like any other filter. This is mainly useful together with a download bounding box larger than the area of interest: the wider data stays available, but the landing page is scoped to what most visitors came for.
- **Map base layers** (Django admin, not `.env`): the backgrounds offered in the map's base layer picker are rows in Dashboard > Map base layers. Three are seeded on install (OSM HOT, ESRI Light Gray Canvas, ESRI World Imagery), so there is nothing to do if those suit you. Add your own by giving a name and either an XYZ tile template (with `{z}`, `{x}`, `{y}` - and no `{r}`, OpenLayers does not support it) or a WMS endpoint plus layer names; a WMS service must serve EPSG:3857. Fill in the attribution, most providers require it. Maps open with the first enabled layer, so the display order also picks the default; untick "is enabled" to hide a layer without losing its settings.
- **Custom predicate**: for filters not expressible via `GBIF_DOWNLOAD_*`, you need a Python override of `GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["PREDICATE_BUILDER"]` (a callable can't be an env var). Copy `djangoproject/local_settings.template.py` to a `local_settings.py`, edit it, and bind-mount it into the container by adding to the `gbif-alert` service in `docker-compose.yml`:
  ```yaml
      volumes:
        - ./local_settings.py:/app/djangoproject/local_settings.py:ro
  ```
  `settings.py` imports it on top of the env-driven config. (Manual deploys instead drop the file at `djangoproject/local_settings.py` directly.)

After editing `.env`, restart the stack:

```
docker compose up -d
```

### Periodic tasks (observation imports + email notifications)

The compose stack includes an `ofelia` scheduler container that calls the two periodic management commands inside the `gbif-alert` container. Schedules are env-configurable:

- `IMPORT_OBSERVATIONS_SCHEDULE` (default: `0 0 2 * * *` - daily at 02:00:00)
- `SEND_NOTIFICATIONS_SCHEDULE` (default: `0 0 14 * * *` - daily at 14:00:00, giving the import a 12-hour window to complete)

These cron expressions are evaluated in the `scheduler` container's timezone, which defaults to UTC.

**The site is unavailable while an import loads data.** Once the GBIF download is ready, the import puts the site in maintenance mode (visitors see a maintenance page, the API answers 503, no notification is sent) until the new observations are in and the previous ones removed - typically minutes, longer for a large instance. Schedule the import when your users are asleep. If an import is killed halfway (e.g. by a redeploy), the maintenance flag is cleared automatically the next time the `gbif-alert` container starts.

If GBIF has not prepared the download after `GBIF_DOWNLOAD_MAX_WAIT_HOURS` (default: `10`), the import gives up. As with any failed import, the admins (`ADMINS`) are emailed and the previous observations stay online. If you move the schedules, keep the import start plus this wait before the notification run.

**Only one import runs at a time.** An import started while another one is still running stops with an error and the admins are emailed; the running import is not affected. This holds however the import was started (schedule, `docker compose exec`, cron). It relies on a PostgreSQL session advisory lock, so the import needs a direct connection to PostgreSQL, or PgBouncer in session mode. PgBouncer in transaction mode is not supported.

**Cron format note:** Ofelia uses a SIX-field cron expression where the leading field is *seconds* (`second minute hour day month dayofweek`), not the standard five-field Unix cron. A five-field expression like `0 2 * * *` is silently misinterpreted as "every hour at HH:02:00" rather than "daily at 02:00". When overriding the defaults, always include the leading `0` for seconds.

**Applying a schedule change:** the schedule is a label on the `gbif-alert`
container. Changing `IMPORT_OBSERVATIONS_SCHEDULE` / `SEND_NOTIFICATIONS_SCHEDULE`
and redeploying updates the label, but Ofelia does not reload it on its own -
restart the scheduler afterwards (`docker compose restart scheduler`) for the
new schedule to take effect.

**Where scheduled output goes:** Ofelia runs each job via `docker exec`, so the
command's output goes to the scheduler, not to `docker compose logs gbif-alert`
(which shows only gunicorn). To debug a scheduled command, run it ad-hoc (below)
to see its output directly, or check `docker compose logs scheduler`, which
records each run's exit status.

To run a job ad-hoc (outside the schedule):

```
docker compose exec gbif-alert python manage.py import_observations
docker compose exec gbif-alert python manage.py send_alert_notifications_email
```

**Notification statistics:** each notification email sent is logged (Django
admin, "Sent notifications"). To print the totals, per month and per user:

```
docker compose exec gbif-alert python manage.py notification_stats
```

Only emails sent since the log was introduced are counted.

### Upgrades

1. Read the [changelog](CHANGELOG.md) for the versions you skip: an entry marked *operator action required* needs a step beyond the two below.
2. Bump `GBIF_ALERT_TAG` in your `.env` (e.g. `2.10.0` -> `2.11.0`). The compose file reads this var via `image: ghcr.io/riparias/gbif-alert:${GBIF_ALERT_TAG:?...}`, so you do not edit the committed compose file itself. The var is required (no baked-in default): an unset or empty value aborts the deploy with a hint instead of silently pulling a stale tag.
3. Pull the new image and recreate:
   ```
   docker compose pull
   docker compose up -d
   ```

The `migrate` service runs first and applies any new database migrations before the app comes back up. Volumes (`valkey_data`, `postgres_data`) are preserved across upgrades.

The bundled `db` service pins a Postgres major version (`postgis/postgis:17-3.5`). Postgres cannot read a data directory written by an older major, so if you ever change that image tag, or re-download a `docker-compose.yml` that does, dump with the old version first, start the new one on an empty volume and restore (see *Backups* below).

#### Upgrading from a version before 2.3.0

Since 2.3.0, downloads and species are keyed on the Catalogue of Life Extended
Release (COL XR) taxonomy instead of GBIF's frozen numeric backbone, and
`import_observations` refuses to run until every species has a COL XR key. After
the upgrade (the `migrate` service has already added the column):

1. Run `docker compose exec gbif-alert python manage.py convert_taxon_keys_to_col`.
   Review the report and curate any UNRESOLVED species in the admin (assign a
   COL XR key manually, or remove species COL cannot match).
2. If you use a custom `PREDICATE_BUILDER` in `local_settings.py`, update it to
   use `gbif_col_taxon_key` and add the COL XR `checklistKey` (see
   `local_settings.template.py`).

### Backups (bundled-db only)

If you use the bundled `db` service, plain `pg_dump` works. The credentials live
in the container's environment, not in your shell, so expand them inside the
container:

```
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup-$(date +%F).dump
```

Schedule via host cron (or external orchestration), and test the restore at least once - a backup that was never restored is a wish. To restore into a fresh, empty database (stop the app first so nothing writes during the restore):

```
docker compose stop gbif-alert rqworker scheduler
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backup-YYYY-MM-DD.dump
docker compose up -d
```

Valkey only holds the cache and the job queue; it needs no backup. Production deployments should prefer a managed Postgres with built-in backups.

### Common operations

| Op | Command |
|---|---|
| App logs | `docker compose logs -f gbif-alert` |
| Scheduler logs | `docker compose logs -f scheduler` |
| Restart app | `docker compose restart gbif-alert` |
| Django shell | `docker compose exec gbif-alert python manage.py shell` |
| Healthcheck | `curl http://localhost:8000/healthz` |
| Rebuild area parts | `docker compose exec gbif-alert python manage.py rebuild_area_parts` |
| Name unnamed datasets | `docker compose exec gbif-alert python manage.py sync_dataset_names` |
| Fetch species pictures | `docker compose exec gbif-alert python manage.py populate_species_images` |

Areas are stored pre-subdivided so that filtering observations by area is fast,
and this is maintained automatically whenever an area is saved. If
`python manage.py check` reports areas without parts - possible after a bulk
import or a database restore that bypassed the application - run the rebuild
command above.

The last two are occasional, not periodic. Every import already names the
datasets it finds; `sync_dataset_names` repairs the names after a GBIF API
outage without waiting for the next import. `populate_species_images` fills the
optional species picture (shown when hovering a species name) from Wikipedia,
falling back to GBIF occurrence media; it never overwrites a picture set by hand
in the admin.

## Run GBIF Alert manually

You don't like Docker and prefer full control? Great.

You'll need to install Python, PostgreSQL, PostGIS, Valkey (or Redis), GDAL and `gettext` (for `compilemessages`) on your system. See [CONTRIBUTING.md](CONTRIBUTING.md) for specific versions. Everything under *Customising your instance*, *Periodic tasks* and *HTTPS is required* above applies to a manual deploy too; only the commands differ.

### One-time setup

1. Create the database and install the PostGIS extension.
2. Create a Python virtual environment and install dependencies: `$ uv sync`.
3. Copy `.env.example` to `.env` (at the project root) and edit:
   ```
   cp .env.example .env
   $EDITOR .env
   ```
   Set at least `SECRET_KEY`, `DATABASE_URL`, `SITE_BASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `SITE_NAME`. See `.env.example` for the full contract and `EMAIL_*` / `GBIF_DOWNLOAD_*` / `MAP_INITIAL_*` settings you'll want for production.
4. (Optional) For settings that cannot be expressed as env vars (e.g. a custom `PREDICATE_BUILDER` callable), copy `djangoproject/local_settings.template.py` to `djangoproject/local_settings.py` and edit. This file is gitignored.
5. Generate the database schema: `$ uv run python manage.py migrate`.
6. Install frontend dependencies: `$ npm install`.
7. Generate static assets: `$ npm run vite-build`.
8. Compile translations: `$ uv run python manage.py compilemessages`.
9. Collect static files: `$ uv run python manage.py collectstatic --no-input`.

### Running

- Web server, as the Docker image runs it:
  ```
  uv run python manage.py clear_stale_import_maintenance
  uv run gunicorn djangoproject.wsgi --bind 127.0.0.1:8000 --workers 3 --limit-request-line 8190
  ```
  The first command clears a maintenance flag left behind by an import that was killed halfway; run it at every start, before gunicorn. `--limit-request-line` raises gunicorn's 4094-byte default: the filter URLs of an alert selecting many species get long. If Nginx sits in front, raise its `large_client_header_buffers` accordingly.
  - Place an Nginx reverse proxy in front for TLS. It must send `X-Forwarded-Proto` (see *HTTPS is required* above), or every request is redirected to itself. On a manual deploy only, you may instead turn the hardening off with the `SECURE_*` variables in `.env.example`.
  - Static files can be served either by Nginx directly (point it at `STATIC_ROOT`) for slightly better performance, or by Gunicorn itself: WhiteNoise is registered in the app and will serve the contents of `STATIC_ROOT`. If you let WhiteNoise handle static files, the Nginx config can be simplified to a pure reverse proxy (no `location /static/ { ... }` block needed). Either approach works.
- RQ worker: `$ uv run python manage.py rqworker default`.
- Cron: schedule `python manage.py import_observations` and `python manage.py send_alert_notifications_email` periodically, e.g. at 02:00 and 14:00 (the import puts the site in maintenance mode while it loads data, and the notification run must start after the import has finished - see *Periodic tasks* above). The import refuses to start while another one is running, so overlapping runs are safe.
- Process supervision (systemd, supervisord, etc.) and env-var loading mechanism are deployment-specific; settings can be provided via a project-root `.env` file or any other mechanism that populates the process environment.

### Upgrading from a legacy manual deploy

Older installs ran `DJANGO_SETTINGS_MODULE=djangoproject.local_settings`, where `local_settings.py` was the full config module (it did `from .settings import *` and loaded its own `djangoproject/.env`). The entry point is now always **`djangoproject.settings`** (the `wsgi`/`asgi`/`manage.py` default). To migrate:

- Stop setting `DJANGO_SETTINGS_MODULE` (or set it explicitly to `djangoproject.settings`).
- Move operational config into the **project-root `.env`** (the only `.env` loaded) or real environment variables - including any Redis credentials in `CACHE_URL`/`RQ_REDIS_URL` (`redis://:PASSWORD@host:6379/0`).
- Keep only Python overrides (e.g. `PREDICATE_BUILDER`, local GDAL paths) in `djangoproject/local_settings.py`, regenerated from `djangoproject/local_settings.template.py` - it is an override layer, **not** an entry point, and must not call `load_dotenv`.

## Funding and acknowledgements

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="static_global/eu-funding/eu-funded-en-negative.png">
  <img src="static_global/eu-funding/eu-funded-en.png" alt="Funded by the European Union" width="280">
</picture>

Development of GBIF Alert has been supported by the European Union's Horizon Europe research and
innovation programme under grant agreements No 101181413 (GuardIAS) and No 101180559 (OneSTOP),
and previously by LIFE RIPARIAS.

Funded by the European Union. Views and opinions expressed are however those of the author(s)
only and do not necessarily reflect those of the European Union or the European Research
Executive Agency (REA). Neither the European Union nor the granting authority can be held
responsible for them.

GBIF Alert was also awarded the first prize of the [GBIF Ebbe Nielsen Challenge 2023](https://www.gbif.org/fr/news/EQgUzZ4YA75BSeLs1naI9/).

The EU emblem above acknowledges the funding of **this software**. It is *not* shown to end users
by default: a running instance displays it only if its operator explicitly opts in, which only
genuinely EU-funded instances may do. See [docs/eu-funding-acknowledgement.md](docs/eu-funding-acknowledgement.md).
