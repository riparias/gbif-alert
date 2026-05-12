"""Targeted tests for the env-driven settings module.

Background
----------
After the settings refactor, `djangoproject/settings.py` is the canonical
self-sufficient settings module. It reads operationally-significant
settings from environment variables (with sensible defaults) and ends
with an optional escape-hatch import of `djangoproject/local_settings.py`
plus a validation block that raises `ImproperlyConfigured` when required
values are missing.

Why these tests exist
---------------------
The vast majority of the test suite runs through the legacy chain
(`DJANGO_SETTINGS_MODULE=djangoproject.local_settings` plus
`from .settings import *` at the top of that file). In that path, the
env-driven block in `settings.py` is mostly overridden by whatever
`local_settings.py` defines, so its behaviour is not directly observed.

These tests pin down the **env-driven path** specifically:
- What happens when the operator boots the app with
  `DJANGO_SETTINGS_MODULE=djangoproject.settings` (the Docker entry
  point, and the path any future PaaS deploy uses)?
- Does each env var actually drive its corresponding setting?
- Does the validation block correctly raise when required vars are missing?

Without these tests, regressions in the env-driven path could land
silently because no other test exercises it.

Test isolation
--------------
Each test runs through `_import_settings()` which re-imports
`djangoproject.settings` from a known state. The user's
`djangoproject/local_settings.py` (the escape hatch consumed by
`settings.py`) is replaced with an empty stub during the import so the
env-driven values are what the test sees - no escape-hatch overrides
sneak in.

The `clean_env` fixture additionally snapshots and restores
`sys.modules` so the mucking inside `_import_settings()` does not leak
into later tests (which would otherwise pick up an empty
`djangoproject.local_settings` and behave unexpectedly).
"""
import sys
import types

import pytest
from django.core.exceptions import ImproperlyConfigured


# Every environment variable the refactored settings module reads. Each
# test starts with all of these unset so its `setenv` calls have a
# predictable effect.
_ENV_VARS_READ_BY_SETTINGS = (
    "SECRET_KEY",
    "DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "SITE_BASE_URL",
    "SITE_NAME",
    "TIME_ZONE",
    "DATABASE_URL",
    "RQ_REDIS_URL",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_USE_TLS",
    "DEFAULT_FROM_EMAIL",
    "SERVER_EMAIL",
    "ADMINS",
    "ENABLED_LANGUAGES",
    "PRIMEVUE_PRIMARY_PALETTE",
    "MAP_INITIAL_ZOOM",
    "MAP_INITIAL_LAT",
    "MAP_INITIAL_LON",
    "GBIF_DOWNLOAD_USERNAME",
    "GBIF_DOWNLOAD_PASSWORD",
    "GBIF_DOWNLOAD_COUNTRY",
    "GBIF_DOWNLOAD_YEAR_MIN",
    "DJANGO_SETTINGS_MODULE",
)

# The two modules `_import_settings()` mutates; the fixture restores them.
_MUTATED_MODULES = ("djangoproject.settings", "djangoproject.local_settings")


@pytest.fixture
def clean_env(monkeypatch):
    """Provide a known-blank environment for env-driven settings tests.

    Two responsibilities:

    1. **Clear every env var the settings module reads.** A developer
       running this suite may have a populated `.env`, exported shell
       variables, or pre-set values from a previous test. Without this
       cleanup, those would leak into the test and silently provide a
       value the test was not asking for.

    2. **Snapshot and restore `sys.modules`** for
       `djangoproject.settings` and `djangoproject.local_settings`.
       `_import_settings()` evicts the real `settings` module and
       replaces `local_settings` with an empty stub - if those mutations
       persisted past the test, subsequent tests in the same pytest
       session would see broken modules and either crash or behave
       strangely.

    Yields the monkeypatch fixture so tests can `.setenv(...)` the
    specific vars they want.
    """
    for var_name in _ENV_VARS_READ_BY_SETTINGS:
        monkeypatch.delenv(var_name, raising=False)

    module_snapshots = {
        name: sys.modules.get(name) for name in _MUTATED_MODULES
    }
    try:
        yield monkeypatch
    finally:
        for name, original in module_snapshots.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def _import_settings():
    """Re-import `djangoproject.settings` so its module body runs against
    the current process environment, isolated from the escape hatch.

    Two steps make this work:

    - **Evict the cached settings module** from `sys.modules`. Without
      this, `import djangoproject.settings` would return the cached
      version whose body ran earlier under different env vars (typically
      when pytest first booted Django).

    - **Stub out the escape hatch** by inserting an empty module under
      `djangoproject.local_settings`. The escape-hatch import in
      `settings.py` (`from djangoproject.local_settings import *`) then
      imports nothing extra, so these tests see exactly what env vars
      produce - not the user's personal `local_settings.py` values.

    Returns the freshly re-imported `djangoproject.settings` module.
    Tests assert on its top-level attributes directly (e.g.
    `settings.SECRET_KEY`, `settings.GBIF_ALERT["SITE_NAME"]`).
    """
    sys.modules.pop("djangoproject.settings", None)
    sys.modules["djangoproject.local_settings"] = types.ModuleType(
        "djangoproject.local_settings"
    )
    import djangoproject.settings  # noqa: WPS433 - module-level import inside fn is the point
    return djangoproject.settings


def test_missing_required_env_raises_improperly_configured(clean_env):
    """Validation block raises `ImproperlyConfigured` when required env
    vars are missing.

    This is the most important behaviour of the refactor: it guarantees
    a misconfigured deploy fails fast at startup with a clear error,
    rather than silently booting with empty secrets / DBs and crashing
    later inside a request handler.

    The error message must mention at least `SECRET_KEY` and
    `DATABASE_URL` so the operator immediately sees what is missing.
    """
    clean_env.setenv("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _import_settings()
    assert "SECRET_KEY" in str(exc_info.value)
    assert "DATABASE_URL" in str(exc_info.value)


def test_minimal_required_env_loads(clean_env):
    """Settings load successfully when the minimum required env vars
    are set: `SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `SITE_BASE_URL`, and
    `DATABASE_URL`.

    This is the "smallest viable deploy" configuration documented in
    `.env.example`. Verifies the env-driven primitives reach their
    Django settings counterparts and `DATABASE_URL` is parsed into the
    `DATABASES` dict.
    """
    clean_env.setenv("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
    clean_env.setenv("SECRET_KEY", "x")
    clean_env.setenv("DJANGO_ALLOWED_HOSTS", "localhost")
    clean_env.setenv("SITE_BASE_URL", "http://localhost")
    clean_env.setenv("DATABASE_URL", "postgis://u:p@h:5432/d")
    settings = _import_settings()
    assert settings.SECRET_KEY == "x"
    assert "localhost" in settings.ALLOWED_HOSTS
    assert settings.DATABASES["default"]["NAME"] == "d"


def test_database_url_uses_postgis_engine(clean_env):
    """`DATABASE_URL=postgis://...` produces the GeoDjango PostGIS engine.

    `dj-database-url` recognises the `postgis://` scheme and maps it to
    `django.contrib.gis.db.backends.postgis`. The app is GIS-dependent
    (PostGIS extensions, hexagon maps), so an accidental fallback to the
    plain `postgresql` backend would break spatial queries silently at
    runtime. This test pins the correct mapping.
    """
    clean_env.setenv("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
    clean_env.setenv("SECRET_KEY", "x")
    clean_env.setenv("DJANGO_ALLOWED_HOSTS", "localhost")
    clean_env.setenv("SITE_BASE_URL", "http://localhost")
    clean_env.setenv("DATABASE_URL", "postgis://u:p@h:5432/d")
    settings = _import_settings()
    assert (
        settings.DATABASES["default"]["ENGINE"]
        == "django.contrib.gis.db.backends.postgis"
    )


def test_gbif_alert_constructed_from_env(clean_env):
    """The `GBIF_ALERT` settings dict is built from per-key env vars.

    Each key inside `GBIF_ALERT` has a corresponding env var
    (`SITE_NAME`, `PRIMEVUE_PRIMARY_PALETTE`, `ENABLED_LANGUAGES`,
    `GBIF_DOWNLOAD_USERNAME`, `MAP_INITIAL_*`, etc.). This test exercises
    a representative subset to catch any regression where one of those
    mappings is dropped or mistyped (e.g. forgetting to convert
    `MAP_INITIAL_LAT` from str to float).

    Also verifies that `ENABLED_LANGUAGES`, a comma-separated env var,
    is parsed into a `tuple` (Django's expected type for `LANGUAGES`).
    """
    clean_env.setenv("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
    clean_env.setenv("SECRET_KEY", "x")
    clean_env.setenv("DJANGO_ALLOWED_HOSTS", "localhost")
    clean_env.setenv("SITE_BASE_URL", "http://localhost")
    clean_env.setenv("DATABASE_URL", "postgis://u:p@h:5432/d")
    clean_env.setenv("SITE_NAME", "Test Site")
    clean_env.setenv("PRIMEVUE_PRIMARY_PALETTE", "emerald")
    clean_env.setenv("ENABLED_LANGUAGES", "en,fr")
    clean_env.setenv("GBIF_DOWNLOAD_USERNAME", "alice")
    clean_env.setenv("MAP_INITIAL_ZOOM", "5")
    clean_env.setenv("MAP_INITIAL_LAT", "50.5")
    settings = _import_settings()
    assert settings.GBIF_ALERT["SITE_NAME"] == "Test Site"
    assert settings.GBIF_ALERT["PRIMEVUE_PRIMARY_PALETTE"] == "emerald"
    assert settings.GBIF_ALERT["ENABLED_LANGUAGES"] == ("en", "fr")
    assert settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["USERNAME"] == "alice"
    assert settings.GBIF_ALERT["MAIN_MAP_CONFIG"]["initialZoom"] == 5
    assert settings.GBIF_ALERT["MAIN_MAP_CONFIG"]["initialLat"] == 50.5


def test_default_time_zone_is_brussels(clean_env):
    """`TIME_ZONE` defaults to `Europe/Brussels` when the env var is
    unset.

    Pre-refactor, this was a hardcoded value in `settings.py`. The
    refactor makes it env-overridable but preserves the historical
    default - operators running in Belgium (the project's main audience)
    keep the same behaviour without needing to set any env var. Other
    operators override via `TIME_ZONE=...`.
    """
    clean_env.setenv("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
    clean_env.setenv("SECRET_KEY", "x")
    clean_env.setenv("DJANGO_ALLOWED_HOSTS", "localhost")
    clean_env.setenv("SITE_BASE_URL", "http://localhost")
    clean_env.setenv("DATABASE_URL", "postgis://u:p@h:5432/d")
    settings = _import_settings()
    assert settings.TIME_ZONE == "Europe/Brussels"


def test_admins_parsed_from_env_string(clean_env):
    """`ADMINS` is parsed from a single env-var string of the form
    `Name1 <a@b>, Name2 <c@d>` into Django's `list[tuple[name, email]]`
    format.

    Django's email error reporting machinery iterates `ADMINS` and uses
    the (name, email) tuples. Encoding the whole list in one env var
    keeps the env contract simple (no `ADMIN_1_NAME`, `ADMIN_1_EMAIL`,
    `ADMIN_2_NAME`, ... proliferation). This test pins the parser's
    behaviour against the format documented in `.env.example`.
    """
    clean_env.setenv("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
    clean_env.setenv("SECRET_KEY", "x")
    clean_env.setenv("DJANGO_ALLOWED_HOSTS", "localhost")
    clean_env.setenv("SITE_BASE_URL", "http://localhost")
    clean_env.setenv("DATABASE_URL", "postgis://u:p@h:5432/d")
    clean_env.setenv("ADMINS", "Alice <a@example.com>, Bob <b@example.com>")
    settings = _import_settings()
    assert ("Alice", "a@example.com") in settings.ADMINS
    assert ("Bob", "b@example.com") in settings.ADMINS
