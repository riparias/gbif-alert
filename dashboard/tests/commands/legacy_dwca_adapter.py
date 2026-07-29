"""Frozen copy of the pre-0.17 DwCA row-path adapter.

The real adapter was replaced by the iter_terms() one in
import_observations.py. This copy is kept deliberately so that:

- test_dwca_adapter_equivalence.py can assert the new adapter produces
  byte-identical RawObservationRow values, and
- benchmarks/bench_parse.py can still measure the 0.16.4 baseline.

Do not "fix" or modernise this file. Its value is that it does not change.
"""

from dwca.darwincore.utils import qualname as qn  # type: ignore
from dwca.rows import CoreRow  # type: ignore

from dashboard.management.commands.import_observations import RawObservationRow

_GBIF = "http://rs.gbif.org/terms/1.0/"

# The 21 terms read by the import, in RawObservationRow field order.
LEGACY_TERMS = [
    _GBIF + "gbifID",
    qn("occurrenceID"),
    qn("occurrenceStatus"),
    qn("year"),
    qn("month"),
    qn("day"),
    qn("decimalLongitude"),
    qn("decimalLatitude"),
    _GBIF + "datasetKey",
    qn("datasetName"),
    _GBIF + "taxonKey",
    _GBIF + "acceptedTaxonKey",
    _GBIF + "speciesKey",
    qn("basisOfRecord"),
    qn("individualCount"),
    qn("coordinateUncertaintyInMeters"),
    qn("identificationVerificationStatus"),
    qn("locality"),
    qn("municipality"),
    qn("recordedBy"),
    qn("references"),
]


def _get_string_data(row: CoreRow, field_name: str) -> str:
    return row.data[field_name].strip()


def _get_int_or_none(row: CoreRow, field_name: str) -> int | None:
    try:
        return int(_get_string_data(row, field_name=field_name))
    except ValueError:
        return None


def _get_float_or_none(row: CoreRow, field_name: str) -> float | None:
    try:
        return float(_get_string_data(row, field_name=field_name))
    except ValueError:
        return None


def legacy_dwca_row_to_raw(row: CoreRow) -> RawObservationRow:
    """Convert a DwCA CoreRow into a typed RawObservationRow."""
    return RawObservationRow(
        gbif_id=int(_get_string_data(row, field_name=_GBIF + "gbifID")),
        occurrence_id=_get_string_data(row, field_name=qn("occurrenceID")),
        occurrence_status=_get_string_data(row, field_name=qn("occurrenceStatus")),
        year=_get_int_or_none(row, qn("year")),
        month=_get_int_or_none(row, qn("month")),
        day=_get_int_or_none(row, qn("day")),
        decimal_longitude=_get_float_or_none(row, qn("decimalLongitude")),
        decimal_latitude=_get_float_or_none(row, qn("decimalLatitude")),
        dataset_key=_get_string_data(row, field_name=_GBIF + "datasetKey"),
        dataset_name=_get_string_data(row, field_name=qn("datasetName")),
        taxon_key=_get_string_data(row, field_name=_GBIF + "taxonKey"),
        accepted_taxon_key=_get_string_data(row, field_name=_GBIF + "acceptedTaxonKey"),
        species_key=_get_string_data(row, field_name=_GBIF + "speciesKey"),
        basis_of_record=_get_string_data(row, field_name=qn("basisOfRecord")),
        individual_count=_get_int_or_none(row, qn("individualCount")),
        coordinate_uncertainty_in_meters=_get_float_or_none(
            row, qn("coordinateUncertaintyInMeters")
        ),
        identification_verification_status=_get_string_data(
            row, field_name=qn("identificationVerificationStatus")
        ),
        locality=_get_string_data(row, field_name=qn("locality")),
        municipality=_get_string_data(row, field_name=qn("municipality")),
        recorded_by=_get_string_data(row, field_name=qn("recordedBy")),
        references=_get_string_data(row, field_name=qn("references")),
    )
