"""End-to-end import benchmark: restore a clean database, then time an import.

Restores gbif_alert_bench from gbif_alert_bench_template before every run, so
each configuration starts from identical state, then runs import_observations
against the given archive and reports a stage breakdown parsed from the
command's own timestamped log lines.

The tail stages (materialized views, unseen migration, previous-observation
delete) are not affected by the DwCA read path. They are reported separately so
they do not dilute the headline.

The import runs as a child process, so the library version must be selected for
the CHILD, not for this script: an outer `uv run --with ...` would not propagate
through the subprocess. Hence the explicit --dwca-version flag.

Safety: this runs a DESTRUCTIVE import (import_observations deletes all
observations from previous imports). It refuses to start unless the RESOLVED
database name contains "bench" - see assert_bench_database() for why an
environment variable alone cannot be trusted here.

Usage:
    PYTHONPATH=. uv run python benchmarks/bench_e2e.py <archive.zip>

    # baseline, for comparison:
    PYTHONPATH=. uv run python benchmarks/bench_e2e.py <archive.zip> --dwca-version 0.16.4
"""

import argparse
import os
import subprocess
import time

BENCH_DB = os.environ.get("BENCH_DB_NAME", "gbif_alert_bench")
TEMPLATE_DB = os.environ.get("BENCH_TEMPLATE_DB", f"{BENCH_DB}_template")
BENCH_SETTINGS = "benchmarks.bench_settings"


def assert_bench_database() -> None:
    """Refuse to run unless the RESOLVED database name looks like a throwaway.

    This is the real safety net, and it deliberately checks the name Django
    actually resolved rather than an environment variable. DATABASE_URL does
    NOT select the database in this project: djangoproject/settings.py imports
    local_settings.py last, and that file defines DATABASES itself, so it wins.
    Setting DATABASE_URL to a bench database still resolves to the developer's
    copy of production. Since import_observations deletes all observations from
    previous imports, running this against that database would destroy it.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", BENCH_SETTINGS)
    import django

    django.setup()
    from django.conf import settings

    name = settings.DATABASES["default"]["NAME"]
    if "bench" not in name:
        raise SystemExit(
            f"REFUSING TO RUN: resolved database is {name!r}, which does not "
            "contain 'bench'. This script runs a destructive import. Check "
            f"DJANGO_SETTINGS_MODULE is {BENCH_SETTINGS}."
        )
    print(f"target database: {name}")


def restore_database() -> None:
    """Drop and recreate the bench database from the template."""
    for sql in (
        f"DROP DATABASE IF EXISTS {BENCH_DB};",
        f"CREATE DATABASE {BENCH_DB} TEMPLATE {TEMPLATE_DB};",
    ):
        subprocess.run(
            ["psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql],
            check=True,
            capture_output=True,
        )


def main(archive: str, dwca_version: str | None) -> int:
    print(f"archive: {archive}")
    print(f"python-dwca-reader: {dwca_version or 'project pin'}")

    assert_bench_database()

    print("restoring database from template...")
    restore_database()

    command = ["uv", "run"]
    if dwca_version is not None:
        command += ["--with", f"python-dwca-reader=={dwca_version}"]
    command += [
        "python",
        "manage.py",
        "import_observations",
        "--source-dwca",
        archive,
    ]

    # The child must resolve the SAME bench database. PYTHONPATH is needed for
    # the benchmarks package to be importable as a settings module.
    env = dict(
        os.environ,
        DJANGO_SETTINGS_MODULE=BENCH_SETTINGS,
        PYTHONPATH=os.getcwd(),
    )
    start = time.perf_counter()
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print(result.stdout[-4000:])
        print(result.stderr[-4000:])
        print(f"IMPORT FAILED after {elapsed:.1f}s")
        return 1

    # The command logs "<ctime>: <message> [peak RSS: N MB]" at each stage. The
    # dots and slashes it prints for per-row progress are stripped out.
    print(f"\ntotal wall clock: {elapsed:.1f}s\n")
    print("stage log:")
    for line in result.stdout.splitlines():
        cleaned = line.lstrip("./")
        if ": " in cleaned and "peak RSS" in cleaned:
            print(f"  {cleaned}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument(
        "--dwca-version",
        default=None,
        help="pin python-dwca-reader to this version for the import child process",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.archive, args.dwca_version))
