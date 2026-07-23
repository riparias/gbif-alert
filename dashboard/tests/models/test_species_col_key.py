"""Tests for Species.gbif_col_taxon_key (the COL XR taxon key).

COL XR keys are alphanumeric (e.g. "C5KM" = Alopochen aegyptiaca), unlike the
frozen integer gbif_taxon_key of the legacy GBIF backbone, which this field sits
alongside rather than replaces.
"""
import pytest
from django.core.exceptions import ValidationError

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


def test_species_with_only_col_key_is_valid(db):
    """A species described after the backbone froze has no legacy key at all."""
    species = Species(name="Newly described sp.", gbif_col_taxon_key="C5KM")
    species.full_clean()  # must not raise
    species.save()
    assert species.pk is not None
    assert species.gbif_taxon_key is None


def test_species_with_only_legacy_key_is_valid(db):
    """The pre-COL workflow still works: add by integer key, convert later."""
    species = Species(name="Legacy sp.", gbif_taxon_key=1234567)
    species.full_clean()  # must not raise
    species.save()
    assert species.gbif_col_taxon_key is None


def test_species_with_neither_key_is_rejected(db):
    """Such a species could never match a download and would break imports."""
    species = Species(name="Keyless sp.")
    with pytest.raises(ValidationError) as excinfo:
        species.full_clean()
    assert "__all__" in excinfo.value.message_dict


def test_two_species_can_both_have_a_null_legacy_key(db):
    """unique=True tolerates multiple NULLs in Postgres - no partial index needed."""
    Species.objects.create(name="First sp.", gbif_col_taxon_key="AAAA")
    Species.objects.create(name="Second sp.", gbif_col_taxon_key="BBBB")
    assert Species.objects.filter(gbif_taxon_key__isnull=True).count() == 2


def test_blank_col_key_counts_as_missing(db):
    """save() normalises "" to NULL only later, so clean() must treat it as absent."""
    species = Species(name="Blank sp.", gbif_col_taxon_key="")
    with pytest.raises(ValidationError):
        species.full_clean()


def test_modelform_rejects_a_species_with_neither_key(db):
    """The admin enforces the rule too - its ModelForm calls full_clean().

    Exercised through modelform_factory rather than SpeciesAdmin.get_form,
    which needs a request and pulls in the translation/import-export mixins.
    """
    from django.forms.models import modelform_factory

    form_class = modelform_factory(
        Species, fields=["name", "gbif_taxon_key", "gbif_col_taxon_key"]
    )
    form = form_class(data={"name": "Keyless sp."})
    assert not form.is_valid()
    assert form.non_field_errors()
