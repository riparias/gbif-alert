import os
import subprocess
from pathlib import Path

import pytest

# pytest-playwright installs an asyncio event loop at session scope.
# Django detects it and refuses synchronous DB operations by default.
# This flag disables that guard - safe in a test context.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"

# Tests must use the built Vite bundle, never the dev server. Force the env-driven
# default off (the _force_vite_built_bundle fixture also overrides any
# local_settings hardcode after settings load).
os.environ["DJANGO_VITE_DEV_MODE"] = "False"


def pytest_sessionstart(session):
    """Build the Vite bundle before any test runs.

    Playwright tests need the pre-built bundle in static_global/vite/.
    This hook runs unconditionally on every pytest invocation.
    """
    subprocess.run(
        ["npm", "run", "vite-build"],
        check=True,
        cwd=Path(__file__).parent,
    )


@pytest.fixture(scope="session", autouse=True)
def _force_vite_built_bundle():
    """Force django-vite dev_mode off so Playwright uses the built bundle.

    With dev_mode on (a developer running `npm run vite-dev` may set
    DJANGO_VITE_DEV_MODE=true or hardcode it in local_settings.py), django-vite
    emits dev-server <script> URLs that 404 in tests - the SPA never mounts and
    every page times out. Override the final setting (after local_settings has
    loaded) and reset django-vite's cached singleton so the built bundle from
    pytest_sessionstart is actually served.
    """
    from django.conf import settings
    from django_vite.core.asset_loader import DjangoViteAssetLoader

    settings.DJANGO_VITE["default"]["dev_mode"] = False
    DjangoViteAssetLoader._instance = None  # rebuild lazily with dev_mode off


@pytest.fixture(autouse=True)
def _relax_api_v2_throttling(monkeypatch):
    """Keep API rate limiting from firing across the shared-cache test suite.

    pytest runs under djangoproject.settings with the real cache, and all test
    requests share one IP, so the production limits would 429 unrelated tests.
    The dedicated throttle tests re-tighten these in their own bodies.
    """
    from dashboard.api_v2 import api_v2_anon_throttle, api_v2_auth_throttle

    monkeypatch.setattr(api_v2_anon_throttle, "num_requests", 10**9)
    monkeypatch.setattr(api_v2_auth_throttle, "num_requests", 10**9)
    yield
