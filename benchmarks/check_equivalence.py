"""Assert the iter_terms adapter and the frozen row adapter agree, row by row.

Not part of the test suite: it needs a multi-gigabyte archive. Run once after
adopting iter_terms, and again after any future python-dwca-reader upgrade.

Usage:
    PYTHONPATH=. uv run python benchmarks/check_equivalence.py <archive.zip>

Exit status is 0 when every row matches, 1 otherwise.
"""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.settings")
django.setup()

from dwca.read import DwCAReader  # type: ignore  # noqa: E402

from dashboard.management.commands.import_observations import (  # noqa: E402
    _IMPORT_TERMS,
    _raw_from_values,
)
from dashboard.tests.commands.legacy_dwca_adapter import (  # noqa: E402
    legacy_dwca_row_to_raw,
)

PROGRESS_EVERY = 100000


def main(archive: str) -> int:
    mismatches = 0
    checked = 0

    # Two independent readers advanced in lockstep: the row path and the
    # iter_terms path over the same archive.
    with DwCAReader(archive) as legacy_reader, DwCAReader(archive) as new_reader:
        legacy_stream = (legacy_dwca_row_to_raw(row) for row in legacy_reader)
        new_stream = (
            _raw_from_values(values) for values in new_reader.iter_terms(_IMPORT_TERMS)
        )

        for legacy_row, new_row in zip(legacy_stream, new_stream, strict=True):
            checked += 1
            if legacy_row != new_row:
                mismatches += 1
                if mismatches <= 10:
                    print(f"MISMATCH at row {checked}:")
                    print(f"  legacy: {legacy_row}")
                    print(f"  new:    {new_row}")
            if checked % PROGRESS_EVERY == 0:
                print(f"  checked {checked} rows, {mismatches} mismatches")

    print(f"checked {checked} rows, {mismatches} mismatches")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
