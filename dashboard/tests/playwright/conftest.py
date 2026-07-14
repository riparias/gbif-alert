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
from playwright.sync_api import Page, expect


# Web-first assertions (expect(...).to_be_visible(), etc.) default to a 5s
# timeout. Now that the suite no longer waits for the (flaky, deprecated)
# "networkidle" load state and instead relies on these assertions to
# synchronise, bump the default so a cold SPA boot in CI - Vue mount plus the
# first data fetch - has enough headroom before an assertion is judged failed.
# Actions (click/fill) keep Playwright's own 30s default.
expect.set_options(timeout=15_000)


@pytest.fixture(autouse=True)
def _drain_server_before_db_teardown(page: Page):
    """Let the live_server finish its in-flight requests before the DB is flushed.

    The SPA fires background requests - notably the map's tile/hexagon queries on
    the index and alert-detail pages - that can still be running on the
    live_server when the test body ends. With the ``networkidle`` waits removed
    the tests finish sooner, so those requests race the ``transaction=True``
    teardown flush and intermittently deadlock against it ("deadlock detected" /
    "database couldn't be flushed", cascading into duplicate-key errors later).

    Aborting the requests client-side is not enough: Django's dev server keeps
    processing a request its worker already started (holding row/table locks)
    even after the client disconnects. The signal that the *server* is done is
    network-idle - every request has been answered - so we wait for it here.

    This is a bounded, best-effort drain, never a synchronisation point: it runs
    only in teardown (the page finished loading long ago, so it settles almost
    instantly), and a timeout is swallowed rather than failing the test. That is
    what makes it different from the in-body ``networkidle`` waits this change
    removed, which failed tests when a still-loading page never went quiet.

    Depending on ``page`` orders this fixture's teardown before the page closes
    and before the DB flush later in teardown.
    """
    yield
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        # Page already closed/crashed, or genuinely never idle: proceed anyway.
        # The DB flush is best-effort protected, not guaranteed, by this drain.
        pass


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
    settings.STORAGES["staticfiles"][
        "BACKEND"
    ] = "django.contrib.staticfiles.storage.StaticFilesStorage"
    # Clear the cached storage instance so the new backend takes effect on the
    # next request (StorageHandler lazily instantiates backends on first use).
    storages._storages.pop("staticfiles", None)  # type: ignore

    # Use the pre-built Vite bundle instead of the dev server.
    settings.DJANGO_VITE["default"]["dev_mode"] = False
    # DjangoViteAssetLoader is a singleton that reads settings once at first use.
    # Reset it so the next template render picks up dev_mode=False and loads the
    # built manifest instead of pointing scripts at the dev server.
    from django_vite.core.asset_loader import DjangoViteAssetLoader  # type: ignore

    DjangoViteAssetLoader._instance = None
