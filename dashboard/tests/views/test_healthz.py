"""Tests for the /healthz endpoint."""
import json

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from maintenance_mode.core import set_maintenance_mode  # type: ignore


@pytest.mark.django_db
def test_healthz_returns_200_and_json():
    client = Client()
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")

    body = json.loads(response.content)
    assert body == {"status": "ok"}


@pytest.mark.django_db
def test_healthz_does_not_require_authentication():
    """Healthz must work for anonymous requests so external probes can hit it."""
    client = Client()
    # No login.
    response = client.get("/healthz")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-healthz-maintenance",
        }
    },
    MAINTENANCE_MODE_STATE_BACKEND="maintenance_mode.backends.CacheBackend",
)
def test_healthz_returns_200_even_in_maintenance_mode():
    """Liveness must stay 200 during maintenance.

    Otherwise the container healthcheck (which hits /healthz) fails, the
    container is marked unhealthy, the reverse proxy drops the route, and users
    get a 404 instead of the 503 maintenance page. So /healthz is exempted from
    maintenance mode (force_maintenance_mode_off on the view).
    """
    cache.clear()
    client = Client()
    set_maintenance_mode(True)
    try:
        # Sanity: maintenance is genuinely on - a normal page is blocked (503).
        assert client.get("/").status_code == 503
        # The liveness probe stays alive.
        assert client.get("/healthz").status_code == 200
    finally:
        set_maintenance_mode(False)
