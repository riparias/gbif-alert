"""Parse-only benchmark for the DwCA read path used by import_observations.

Not part of the test suite. Run the variants back to back, in one sitting, on an
idle machine. See README.md for methodology and recorded numbers.

Three measurement points:

    # baseline: 0.16.4, row path
    PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py <archive> rows

    # upgrade: 0.17.1, row path
    PYTHONPATH=. uv run python benchmarks/bench_parse.py <archive> rows

    # iter_terms: 0.17.1, positional path
    PYTHONPATH=. uv run python benchmarks/bench_parse.py <archive> iter_terms

The "rows" variant deliberately reproduces the pre-change behaviour of BOTH
passes, including building a full RawObservationRow during discovery, because
that is what the code did. Comparing it against "iter_terms" therefore shows
the combined effect of the new API and the narrowed discovery pass.
"""

import os
import resource
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
django.setup()

from dwca.read import DwCAReader  # type: ignore  # noqa: E402

from dashboard.management.commands.import_observations import (  # noqa: E402
    _DISCOVERY_TERMS,
    _IMPORT_TERMS,
    _raw_from_values,
    discover_datasets_and_basis_of_record,
)
from dashboard.tests.commands.legacy_dwca_adapter import (  # noqa: E402
    legacy_dwca_row_to_raw,
)


def _peak_rss_mb() -> float:
    """Peak RSS so far, in MB. Process-wide high-water mark: it never
    decreases within a run, so compare it across invocations of this script,
    not across the lines of one invocation."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / (1024 * 1024)  # bytes -> MB
    return peak / 1024  # KB -> MB


def timed(label: str, fn) -> None:
    start = time.perf_counter()
    n = fn()
    elapsed = time.perf_counter() - start
    print(f"  {label:<44}{elapsed:6.2f}s  n={n}  peak={_peak_rss_mb():.0f}MB")


def bench_rows(archive: str) -> None:
    """The pre-change code path. Works on 0.16.4 and on 0.17.x."""

    def open_only():
        with DwCAReader(archive):
            return "opened"

    def discovery():
        # Pre-change behaviour: build the full row, then read three fields.
        with DwCAReader(archive) as dwca:
            triples = (
                (raw.dataset_key, raw.dataset_name, raw.basis_of_record)
                for raw in (legacy_dwca_row_to_raw(row) for row in dwca)
            )
            datasets, bor = discover_datasets_and_basis_of_record(triples)
            return f"{len(datasets)} datasets, {len(bor)} bor"

    def full_pass():
        count = 0
        with DwCAReader(archive) as dwca:
            for row in dwca:
                legacy_dwca_row_to_raw(row)
                count += 1
        return count

    timed("open archive", open_only)
    timed("discovery pass (full row built)", discovery)
    timed("full RawObservationRow pass", full_pass)


def bench_iter_terms(archive: str) -> None:
    """The post-change code path. Requires 0.17+."""

    def open_only():
        with DwCAReader(archive, skip_metadata=True):
            return "opened"

    def discovery():
        with DwCAReader(archive, skip_metadata=True) as dwca:
            triples = (
                (a.strip(), b.strip(), c.strip())
                for a, b, c in dwca.iter_terms(_DISCOVERY_TERMS)
            )
            datasets, bor = discover_datasets_and_basis_of_record(triples)
            return f"{len(datasets)} datasets, {len(bor)} bor"

    def full_pass():
        count = 0
        with DwCAReader(archive, skip_metadata=True) as dwca:
            for values in dwca.iter_terms(_IMPORT_TERMS):
                _raw_from_values(values)
                count += 1
        return count

    timed("open archive", open_only)
    timed("discovery pass (3 terms)", discovery)
    timed("full RawObservationRow pass", full_pass)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in ("rows", "iter_terms"):
        print(__doc__)
        raise SystemExit(2)

    import importlib.metadata as md

    archive_path, variant = sys.argv[1], sys.argv[2]
    version = md.version("python-dwca-reader")
    print(f"archive: {archive_path}")
    print(f"python-dwca-reader {version}, variant {variant}")

    if variant == "rows":
        bench_rows(archive_path)
    else:
        bench_iter_terms(archive_path)
