from django.core.cache import cache
from django.test import override_settings
from maintenance_mode.core import (  # type: ignore
    get_maintenance_mode,
    set_maintenance_mode,
)

from dashboard.maintenance import (
    MAINTENANCE_IMPORT_MARKER,
    disable_maintenance_for_import,
    enable_maintenance_for_import,
)

# LocMemCache + CacheBackend so the tests are hermetic (no Valkey), matching
# dashboard/tests/test_maintenance_mode.py.
CACHE_OVERRIDE = dict(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-maintenance-self-heal",
        }
    },
    MAINTENANCE_MODE_STATE_BACKEND="maintenance_mode.backends.CacheBackend",
)


@override_settings(**CACHE_OVERRIDE)
def test_enable_sets_maintenance_and_marker():
    cache.clear()
    enable_maintenance_for_import()
    assert get_maintenance_mode() is True
    assert cache.get(MAINTENANCE_IMPORT_MARKER) is True


@override_settings(**CACHE_OVERRIDE)
def test_disable_clears_maintenance_and_marker():
    cache.clear()
    enable_maintenance_for_import()
    disable_maintenance_for_import()
    assert get_maintenance_mode() is False
    assert cache.get(MAINTENANCE_IMPORT_MARKER) is None
