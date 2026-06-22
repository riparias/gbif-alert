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
- The available languages in the interface: English, French and Dutch are currently supported.
- Website texts, e.g. the introduction on the home page, the footer content and the "about this site" page.
- The primary color theme of the interface, via the `PRIMEVUE_PRIMARY_PALETTE`
  setting (e.g. `indigo`, `emerald`, `blue`, `rose`; see `.env.example`).

## Dependencies

Technically speaking, GBIF Alert is a [Django](https://www.djangoproject.com/)-based website, with the following dependencies:

- [Python](https://www.python.org/)
- [PostgreSQL](https://www.postgresql.org/) with [PostGIS](https://postgis.net/)
- [Redis](https://redis.io/)
- [NPM](https://www.npmjs.com/) (for frontend assets)

(see [CONTRIBUTING.md](CONTRIBUTING.md) for specific versions and more details on the inner working of the tool).

While a manual installation of those components is possible, we recommend using [Docker Compose](https://docs.docker.com/get-started/08_using_compose/) to install and run GBIF Alert. 
It will make your life much easier!

Please note that in order to run a production GBIF Alert instance, you will need to have access to the following resources:

- A server running Linux with a public IP address (and a domain name)
- Access to an [SMTP server](https://nl.wikipedia.org/wiki/Simple_Mail_Transfer_Protocol) (for sending notification emails)

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

2. Download the two artefacts from the release tag (replace `v1.10.0` with the version you want):
   ```
   curl -O https://raw.githubusercontent.com/riparias/gbif-alert/v1.10.0/docker-compose.yml
   curl -O https://raw.githubusercontent.com/riparias/gbif-alert/v1.10.0/.env.example
   ```

3. Copy the env template and edit:
   ```
   cp .env.example .env
   $EDITOR .env
   ```

   Set at minimum: `SECRET_KEY`, `DATABASE_URL`, `SITE_BASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_NAME`, and `GBIF_ALERT_TAG` (the image tag to pull - e.g. `devel` or a release like `1.11.0`; required, no default). See `.env.example` for the full contract. The Docker stack is **entirely env-driven** - you do not need a `local_settings.py`. (For a Python-only override like a custom `PREDICATE_BUILDER`, see the Custom predicate note below.)

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
  with your proxy config for TLS and routing.

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
- **Map default view**: `MAP_INITIAL_ZOOM`, `MAP_INITIAL_LAT`, `MAP_INITIAL_LON`.
- **Languages**: `ENABLED_LANGUAGES` (comma-separated subset of `en,fr,nl`).
- **Email**: SMTP by default (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`). To send through **Amazon SES with an IAM role** instead of SMTP credentials, set `EMAIL_BACKEND=django_ses.SESBackend` and `AWS_SES_REGION_NAME` (e.g. `eu-west-1`); the credentials are then taken from the ambient AWS role (ECS task role / EC2 instance role), so no SMTP user/password is stored. `DEFAULT_FROM_EMAIL` must be a verified SES identity.
- **GBIF download filter**: `GBIF_DOWNLOAD_USERNAME`, `GBIF_DOWNLOAD_PASSWORD`, `GBIF_DOWNLOAD_COUNTRY`, `GBIF_DOWNLOAD_YEAR_MIN`. The default predicate builder uses these to construct the download filter.
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

### Upgrades

1. Bump `GBIF_ALERT_TAG` in your `.env` (e.g. `1.10.0` -> `1.11.0`). The compose file reads this var via `image: ghcr.io/riparias/gbif-alert:${GBIF_ALERT_TAG:?...}`, so you do not edit the committed compose file itself. The var is required (no baked-in default): an unset or empty value aborts the deploy with a hint instead of silently pulling a stale tag.
2. Pull the new image and recreate:
   ```
   docker compose pull
   docker compose up -d
   ```

The `migrate` service runs first and applies any new database migrations before the app comes back up. Volumes (`valkey_data`, `postgres_data`) are preserved across upgrades.

### Backups (bundled-db only)

If you use the bundled `db` service, plain `pg_dump` works:

```
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup-$(date +%F).sql
```

Schedule via host cron (or external orchestration). Production deployments should prefer a managed Postgres with built-in backups.

### Common operations

| Op | Command |
|---|---|
| App logs | `docker compose logs -f gbif-alert` |
| Scheduler logs | `docker compose logs -f scheduler` |
| Restart app | `docker compose restart gbif-alert` |
| Django shell | `docker compose exec gbif-alert python manage.py shell` |
| Healthcheck | `curl http://localhost:8000/healthz` |

## Run GBIF Alert manually

You don't like Docker and prefer full control? Great.

You'll need to install Python, PostgreSQL, PostGIS and Redis (or Valkey) on your system. See [CONTRIBUTING.md](CONTRIBUTING.md) for specific versions.

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

- Web server: `$ uv run gunicorn djangoproject.wsgi`. Place an Nginx reverse proxy in front for TLS and (optionally) static-file serving.
  - Static files can be served either by Nginx directly (point it at `STATIC_ROOT`) for slightly better performance, or by Gunicorn itself: WhiteNoise is registered in the app and will serve the contents of `STATIC_ROOT`. If you let WhiteNoise handle static files, the Nginx config can be simplified to a pure reverse proxy (no `location /static/ { ... }` block needed). Either approach works.
- RQ worker: `$ uv run python manage.py rqworker default`.
- Cron: schedule `python manage.py import_observations` and `python manage.py send_alert_notifications_email` periodically.
- Process supervision (systemd, supervisord, etc.) and env-var loading mechanism are deployment-specific; settings can be provided via a project-root `.env` file or any other mechanism that populates the process environment.

### Upgrading from a legacy manual deploy

Older installs ran `DJANGO_SETTINGS_MODULE=djangoproject.local_settings`, where `local_settings.py` was the full config module (it did `from .settings import *` and loaded its own `djangoproject/.env`). The entry point is now always **`djangoproject.settings`** (the `wsgi`/`asgi`/`manage.py` default). To migrate:

- Stop setting `DJANGO_SETTINGS_MODULE` (or set it explicitly to `djangoproject.settings`).
- Move operational config into the **project-root `.env`** (the only `.env` loaded) or real environment variables - including any Redis credentials in `CACHE_URL`/`RQ_REDIS_URL` (`redis://:PASSWORD@host:6379/0`).
- Keep only Python overrides (e.g. `PREDICATE_BUILDER`, local GDAL paths) in `djangoproject/local_settings.py`, regenerated from `djangoproject/local_settings.template.py` - it is an override layer, **not** an entry point, and must not call `load_dotenv`.
