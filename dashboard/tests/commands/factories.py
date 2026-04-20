"""Helpers for building RawObservationRow fixtures in tests.

Lets logic-focused tests drive the full import pipeline from plain Python
literals instead of opaque DwCA zip files. The DwCA format is still
exercised by a separate, smaller set of tests.
"""

from dashboard.management.commands.import_observations import (
    RawObservationRow,
    run_import,
)


def make_raw_row(**overrides) -> RawObservationRow:
    """Build a RawObservationRow with sensible defaults.

    Pass keyword arguments to override any field. Defaults produce a
    usable, non-skipped row referring to the Lixus bardanae taxon
    (gbif_taxon_key=1224034), basis HUMAN_OBSERVATION, somewhere in
    Belgium in May 2023.
    """
    defaults = dict(
        gbif_id=1,
        occurrence_id="occ-1",
        occurrence_status="PRESENT",
        year=2023,
        month=5,
        day=15,
        decimal_longitude=5.0,
        decimal_latitude=50.0,
        dataset_key="ds-key-1",
        dataset_name="Dataset 1",
        taxon_key=1224034,
        accepted_taxon_key=1224034,
        species_key=1224034,
        basis_of_record="HUMAN_OBSERVATION",
        individual_count=1,
        coordinate_uncertainty_in_meters=10.0,
        identification_verification_status="",
        locality="",
        municipality="",
        recorded_by="",
        references="",
    )
    return RawObservationRow(**{**defaults, **overrides})


def run_import_with_rows(
    rows: list[RawObservationRow],
    *,
    gbif_download_id: str = "test-dl",
    gbif_predicate: dict | None = None,
):
    """Drive the full import pipeline from an in-memory list of rows.

    The factory given to run_import is called twice (once for discovery,
    once for insert); ``iter(rows)`` produces a fresh iterator each call.
    """
    return run_import(
        lambda: iter(rows),
        gbif_download_id=gbif_download_id,
        gbif_predicate=gbif_predicate,
    )
