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
    (COL taxon key 3VPFV), basis HUMAN_OBSERVATION, somewhere in
    Belgium in May 2023.

    The taxon keys are COL XR keys (alphanumeric), matching what a real
    GBIF download interpreted against the COL XR checklist returns.
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
        taxon_key="3VPFV",
        accepted_taxon_key="3VPFV",
        species_key="3VPFV",
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

    run_import takes two factories: one yielding the narrow
    (dataset_key, dataset_name, basis_of_record) triples used by the
    discovery pass, one yielding the full rows used by the insert pass.
    Both are derived from the same list here, and each call rebuilds its
    iterator so the two passes stay independent.
    """
    return run_import(
        lambda: iter(rows),
        lambda: (
            (row.dataset_key, row.dataset_name, row.basis_of_record) for row in rows
        ),
        gbif_download_id=gbif_download_id,
        gbif_predicate=gbif_predicate,
    )
