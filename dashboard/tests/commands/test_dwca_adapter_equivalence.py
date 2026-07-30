"""The iter_terms adapter must produce exactly what the row adapter produced.

python-dwca-reader 0.17 is new, and iter_terms() differs from the row path in
two ways that could silently change imported data: it returns unstripped
values, and it resolves terms up front rather than per row. This test pins the
two paths together over the committed fixture. The same comparison is run over
a real 1M-row archive by benchmarks/check_equivalence.py, which is too big for
the test suite.
"""

from pathlib import Path

from dwca.read import DwCAReader  # type: ignore

from dashboard.management.commands.import_observations import (
    _IMPORT_TERMS,
    _raw_from_values,
)
from dashboard.tests.commands.legacy_dwca_adapter import (
    LEGACY_TERMS,
    legacy_dwca_row_to_raw,
)

SAMPLE_DWCA = Path(__file__).parent / "sample_data" / "gbif_download.zip"


def test_import_terms_match_the_legacy_term_list():
    """The new term list must request the same terms, in the same order, as
    the fields of RawObservationRow - otherwise values land in wrong fields."""
    assert _IMPORT_TERMS == LEGACY_TERMS


def test_iter_terms_adapter_matches_row_adapter_on_the_fixture():
    """Every row of the fixture must convert identically via both paths."""
    with DwCAReader(SAMPLE_DWCA) as dwca:
        legacy_rows = [legacy_dwca_row_to_raw(row) for row in dwca]

    with DwCAReader(SAMPLE_DWCA) as dwca:
        new_rows = [
            _raw_from_values(values) for values in dwca.iter_terms(_IMPORT_TERMS)
        ]

    assert len(new_rows) == len(legacy_rows)
    assert new_rows == legacy_rows


def test_fixture_is_not_empty():
    """Guards the two tests above: comparing two empty lists would pass."""
    with DwCAReader(SAMPLE_DWCA) as dwca:
        assert sum(1 for _ in dwca) > 0
