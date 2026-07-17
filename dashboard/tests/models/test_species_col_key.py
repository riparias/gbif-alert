"""Tests for Species.gbif_col_taxon_key (the COL XR taxon key).

COL XR keys are alphanumeric (e.g. "C5KM" = Alopochen aegyptiaca), unlike the
frozen integer gbif_taxon_key of the legacy GBIF backbone, which this field sits
alongside rather than replaces.
"""
import pytest
from dashboard.models import Species

pytestmark = pytest.mark.django_db


def test_species_has_col_taxon_key_field_defaulting_to_none():
    """A new species starts with no COL key.

    Why NULL rather than "": the whole app reads NULL as "not yet resolved" (the
    import preflight guard blocks on it, the conversion command fills it), and
    the field is unique, so blanks must be NULL to coexist.
    """
    sp = Species.objects.create(name="Testus colus", gbif_taxon_key=900001)
    assert sp.gbif_col_taxon_key is None


def test_species_col_taxon_key_stored_and_in_as_dict():
    """The COL key round-trips and is exposed to the frontend alongside the
    legacy key - the API surface is additive, so both keys must be present."""
    sp = Species.objects.create(
        name="Testus colus", gbif_taxon_key=900002, gbif_col_taxon_key="C5KM"
    )
    assert sp.gbif_col_taxon_key == "C5KM"
    d = sp.as_dict
    assert d["gbifColTaxonKey"] == "C5KM"
    assert d["gbifTaxonKey"] == 900002  # legacy key still present (non-breaking)


def test_blank_col_taxon_key_is_normalised_to_none():
    """A blank COL key is persisted as NULL, not "".

    Why: the field is admin-editable, and a Django ModelForm saves an empty
    field as "". A "" would pass the import guard's "no key" check, then be
    dropped from the species match hash - silently unmonitoring the species -
    and a second "" would collide on the unique constraint. Normalising to NULL
    closes both holes.
    """
    sp = Species.objects.create(
        name="Blankus", gbif_taxon_key=900003, gbif_col_taxon_key=""
    )
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key is None

    # A second blank species must also be storable (two "" would have collided).
    sp2 = Species.objects.create(
        name="Blankus Two", gbif_taxon_key=900004, gbif_col_taxon_key=""
    )
    sp2.refresh_from_db()
    assert sp2.gbif_col_taxon_key is None
