import pytest
from dashboard.models import Species

pytestmark = pytest.mark.django_db


def test_species_has_col_taxon_key_field_defaulting_to_none():
    sp = Species.objects.create(name="Testus colus", gbif_taxon_key=900001)
    assert sp.gbif_col_taxon_key is None


def test_species_col_taxon_key_stored_and_in_as_dict():
    sp = Species.objects.create(
        name="Testus colus", gbif_taxon_key=900002, gbif_col_taxon_key="C5KM"
    )
    assert sp.gbif_col_taxon_key == "C5KM"
    d = sp.as_dict
    assert d["gbifColTaxonKey"] == "C5KM"
    assert d["gbifTaxonKey"] == 900002  # legacy key still present (non-breaking)


def test_blank_col_taxon_key_is_normalised_to_none():
    # A blank value (e.g. from an admin ModelForm) must persist as NULL, not "",
    # so it reads as "not yet resolved" everywhere and does not collide on the
    # unique constraint.
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
