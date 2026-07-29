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


def _psql(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True,
        text=True,
    )


def restore_database(attempts: int = 30, delay_seconds: int = 10) -> None:
    """Drop and recreate the bench database from the template.

    Any other session has to go first: DROP DATABASE fails while anything is
    connected, and the previous run's connection can still be closing well after
    that run's process exited - observed more than a minute later. So terminate
    stragglers, then retry, because termination is not instantaneous either.

    Retries persistently - about five minutes by default - because the failures
    seen here are transient and the thing they abort is expensive. On this
    machine Postgres.app intermittently refuses connections with 'failed to
    verify "trust" authentication / You did not confirm the permission dialog',
    clearing again on its own a few minutes later. A short retry window turned
    that blip into a lost 76-minute benchmark run twice.

    psql's stderr is reported on failure. The earlier version passed check=True
    with captured output, which raised a CalledProcessError showing the command
    but not the reason, which is why the first occurrence was opaque.
    """
    for attempt in range(1, attempts + 1):
        _psql(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{BENCH_DB}' AND pid <> pg_backend_pid();"
        )
        dropped = _psql(f"DROP DATABASE IF EXISTS {BENCH_DB};")
        if dropped.returncode == 0:
            created = _psql(f"CREATE DATABASE {BENCH_DB} TEMPLATE {TEMPLATE_DB};")
            if created.returncode == 0:
                return
            raise SystemExit(f"could not create {BENCH_DB}: {created.stderr.strip()}")

        if attempt == attempts:
            raise SystemExit(
                f"could not drop {BENCH_DB} after {attempts} attempts: "
                f"{dropped.stderr.strip()}"
            )
        print(f"  drop failed (attempt {attempt}), retrying: {dropped.stderr.strip()}")
        time.sleep(5)


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
