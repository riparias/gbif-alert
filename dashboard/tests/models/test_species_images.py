import pytest
from dashboard.models import Species


@pytest.mark.django_db
def test_species_image_fields_default_blank():
    sp = Species.objects.create(name="Testus specius", gbif_taxon_key=999001)
    assert sp.image_url == ""
    assert sp.image_source_url == ""
    assert sp.image_attribution == ""
    assert sp.image_license == ""
    assert sp.image_source_type == ""
    assert sp.has_image is False


@pytest.mark.django_db
def test_species_has_image_true_when_url_set():
    sp = Species.objects.create(
        name="Testus specius",
        gbif_taxon_key=999002,
        image_url="https://example.org/x.jpg",
        image_source_type=Species.ImageSourceType.WIKIPEDIA,
    )
    assert sp.has_image is True
    assert sp.image_source_type == "wikipedia"
