"""Tests for SpeciesResource, the django-import-export resource behind the
admin's bulk CSV/XLSX import for Species.

These pin that the resource enforces Species.clean()'s "at least one taxon
key" rule during import - a rule that used to only be enforced by the admin
ModelForm and the v2 API, and was silently bypassable via a bulk import
(see dashboard/admin.py, SpeciesResource.Meta.clean_model_instances).
"""

import pytest
import tablib  # type: ignore

from dashboard.admin import SpeciesResource
from dashboard.models import Species

pytestmark = pytest.mark.django_db


def test_import_rejects_species_with_neither_taxon_key():
    """A row with no taxon key at all must be rejected, not silently stored.

    Such a species would block the instance's next import_observations run.
    """
    dataset = tablib.Dataset(headers=["name", "gbif_taxon_key", "gbif_col_taxon_key"])
    dataset.append(["Keyless sp.", "", ""])

    result = SpeciesResource().import_data(dataset, dry_run=True)

    assert result.has_validation_errors()
    assert len(result.invalid_rows) == 1
    assert not Species.objects.filter(name="Keyless sp.").exists()


def test_import_accepts_species_with_only_col_key():
    """A COL-only species (no legacy GBIF key) must still import cleanly.

    This is the whole point of the branch: a species described after the GBIF
    backbone froze has no legacy key, and that is valid.
    """
    dataset = tablib.Dataset(headers=["name", "gbif_taxon_key", "gbif_col_taxon_key"])
    dataset.append(["Newly described sp.", "", "C5KM"])

    result = SpeciesResource().import_data(dataset, dry_run=True)

    assert not result.has_validation_errors()
    assert not result.has_errors()
