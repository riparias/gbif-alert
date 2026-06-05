import os
import subprocess
from pathlib import Path

import pytest

# pytest-playwright installs an asyncio event loop at session scope.
# Django detects it and refuses synchronous DB operations by default.
# This flag disables that guard - safe in a test context.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"


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
