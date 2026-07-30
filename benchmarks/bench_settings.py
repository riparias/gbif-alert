"""Django settings that actually point at the throwaway benchmark database.

DATABASE_URL cannot be used for this. djangoproject/settings.py builds DATABASES
from it, but then imports djangoproject/local_settings.py at the very end, and
that file defines DATABASES itself - so local_settings wins and the benchmark
would silently run against the developer's real database.

This module star-imports the project settings (which pulls local_settings in as
a side effect) and then overrides DATABASES afterwards, so it is the last word.

Usage:
    DJANGO_SETTINGS_MODULE=benchmarks.bench_settings PYTHONPATH=. uv run ...

Set BENCH_DB_NAME to target a different throwaway database - for instance a
clone of a real database, seeded with real users and alerts, so that a run
measures a realistic re-import rather than a first import into an empty table.
The name must still contain "bench": every script that writes re-checks the
RESOLVED name, so a typo cannot point this at a real database.
"""

import os

from djangoproject.settings import *  # noqa: F401, F403

BENCH_DB_NAME = os.environ.get("BENCH_DB_NAME", "gbif_alert_bench")

if "bench" not in BENCH_DB_NAME:
    raise RuntimeError(
        f"BENCH_DB_NAME={BENCH_DB_NAME!r} does not contain 'bench'. These "
        "settings are only ever for throwaway databases."
    )

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": BENCH_DB_NAME,
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}
