"""Pytest configuration for Playwright browser tests.

Two settings from local_settings.py are incompatible with headless browser tests
and must be overridden before any HTTP requests are made:

1. ManifestStaticFilesStorage (default in settings.py) generates hashed URLs
   (e.g. show_body.63e79d9118ab.css). The staticfiles finders used by the
   live_server only look in STATICFILES_DIRS and app static/ dirs - not in
   STATIC_ROOT where collectstatic puts hashed files. So hashed static URLs
   return 404, including show_body.css, which means `html { display: none }`
   (set in base.html to prevent FOUC) is never overridden. Every element on
   every page becomes invisible to Playwright, causing all assertions to fail.

2. local_settings.py sets DJANGO_VITE dev_mode=True for use with the Vite dev
   server. Without that dev server running, {% vite_asset %} points to
   http://localhost:... and the JS bundle never loads. Vue never mounts, so no
   PrimeVue components render.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def playwright_test_settings() -> None:
    """Switch to test-compatible static file and Vite settings.

    Session-scoped so it runs once before the live_server is first requested.
    Settings are read per-request (not cached at server startup), so changes
    made here take effect for all subsequent HTTP requests in the session.
    """
    from django.conf import settings
    from django.core.files.storage import storages

    # Use non-hashed storage so staticfiles finders can serve files by their
    # original names from STATICFILES_DIRS.
    settings.STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )
    # Clear the cached storage instance so the new backend takes effect on the
    # next request (StorageHandler lazily instantiates backends on first use).
    storages._storages.pop("staticfiles", None)

    # Use the pre-built Vite bundle instead of the dev server.
    settings.DJANGO_VITE["default"]["dev_mode"] = False
    # DjangoViteAssetLoader is a singleton that reads settings once at first use.
    # Reset it so the next template render picks up dev_mode=False and loads the
    # built manifest instead of pointing scripts at the dev server.
    from django_vite.core.asset_loader import DjangoViteAssetLoader
    DjangoViteAssetLoader._instance = None
