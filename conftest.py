import os
import subprocess
from pathlib import Path

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
