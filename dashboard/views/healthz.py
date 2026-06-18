"""Lightweight liveness probe.

Returns HTTP 200 with `{"status": "ok"}` so external probes (compose
healthcheck, Dokploy/Traefik, ECS ALB, etc.) can verify the app is alive.

Intentionally does NOT touch the database. A failing DB should still let
`/healthz` return 200 - the probe is for "is the gunicorn process alive
and serving requests", not "is the entire stack healthy". Adding a DB
check would couple liveness to readiness and cause cascading restarts.
"""
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from maintenance_mode.decorators import force_maintenance_mode_off  # type: ignore


# `force_maintenance_mode_off`: liveness must stay 200 even during maintenance,
# or the container healthcheck fails -> the container is marked unhealthy -> the
# reverse proxy drops the route -> users get a 404 instead of the 503
# maintenance page. The process is alive and serving (it serves that page), so
# the probe should say so.
@force_maintenance_mode_off
@require_GET
@never_cache
def healthz(_request):
    return JsonResponse({"status": "ok"})
