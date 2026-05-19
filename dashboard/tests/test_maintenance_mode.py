"""Behavioural test for the maintenance_mode toggle.

Pins the round-trip behaviour of `set_maintenance_mode` /
`get_maintenance_mode` through the configured `CacheBackend`. The
project switched from `LocalFileBackend` to `CacheBackend` after a
production incident where root-owned `maintenance_mode_state.txt` from
an ofelia exec locked out gunicorn workers. The settings-level pins in
`test_settings.py` make sure the backend reference is correct; this
test makes sure the toggle behaviour through the cache is correct too,
so a future library regression or cache misconfiguration would surface
here rather than in production logs.

LocMemCache is used (the test-time default with no Redis env vars) so
the test is hermetic and does not require a running Valkey.
"""
from django.core.cache import cache
from django.test import override_settings

from maintenance_mode.core import (  # type: ignore
    get_maintenance_mode,
    set_maintenance_mode,
)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-maintenance-mode",
        }
    },
    MAINTENANCE_MODE_STATE_BACKEND="maintenance_mode.backends.CacheBackend",
)
def test_maintenance_mode_round_trips_through_cache():
    cache.clear()
    set_maintenance_mode(False)
    assert get_maintenance_mode() is False

    set_maintenance_mode(True)
    assert get_maintenance_mode() is True

    set_maintenance_mode(False)
    assert get_maintenance_mode() is False
