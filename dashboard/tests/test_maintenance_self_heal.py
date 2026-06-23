from django.core.cache import cache
from django.test import override_settings
from maintenance_mode.core import (  # type: ignore
    get_maintenance_mode,
    set_maintenance_mode,
)

from dashboard.maintenance import (
    MAINTENANCE_IMPORT_MARKER,
    clear_stale_import_maintenance,
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


@override_settings(**CACHE_OVERRIDE)
def test_clear_stale_clears_import_set_maintenance():
    cache.clear()
    enable_maintenance_for_import()  # maintenance ON + marker
    clear_stale_import_maintenance()
    assert get_maintenance_mode() is False
    assert cache.get(MAINTENANCE_IMPORT_MARKER) is None


@override_settings(**CACHE_OVERRIDE)
def test_clear_stale_leaves_manual_maintenance():
    cache.clear()
    set_maintenance_mode(True)  # manual: no marker
    clear_stale_import_maintenance()
    assert get_maintenance_mode() is True  # left untouched


@override_settings(**CACHE_OVERRIDE)
def test_clear_stale_drops_orphan_marker_when_off():
    cache.clear()
    cache.set(MAINTENANCE_IMPORT_MARKER, True, None)  # orphan marker, maintenance off
    clear_stale_import_maintenance()
    assert get_maintenance_mode() is False
    assert cache.get(MAINTENANCE_IMPORT_MARKER) is None


@override_settings(**CACHE_OVERRIDE)
def test_clear_stale_swallows_cache_errors(monkeypatch):
    cache.clear()
    set_maintenance_mode(True)

    def boom(*args, **kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr("dashboard.maintenance.get_maintenance_mode", boom)
    clear_stale_import_maintenance()  # must not raise
