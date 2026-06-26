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


@pytest.mark.django_db
def test_species_as_dict_includes_image_fields():
    sp = Species.objects.create(
        name="Testus specius",
        gbif_taxon_key=999003,
        image_url="https://example.org/x.jpg",
        image_source_url="https://en.wikipedia.org/wiki/Testus",
        image_attribution="Jane Doe",
        image_license="CC BY-SA 4.0",
        image_source_type=Species.ImageSourceType.WIKIPEDIA,
    )
    d = sp.as_dict
    assert d["imageUrl"] == "https://example.org/x.jpg"
    assert d["imageSourceUrl"] == "https://en.wikipedia.org/wiki/Testus"
    assert d["imageAttribution"] == "Jane Doe"
    assert d["imageLicense"] == "CC BY-SA 4.0"
    assert d["imageSourceType"] == "wikipedia"


@pytest.mark.django_db
def test_species_image_url_accepts_long_url():
    # Real Wikimedia thumbnail URLs routinely exceed Django's default URLField
    # length of 200 (e.g. the Pallas's squirrel thumbnail is 216 chars). The
    # field must store them without truncation.
    long_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/" + "a" * 300 + ".jpg"
    assert len(long_url) > 200
    sp = Species.objects.create(
        name="Longus urlus",
        gbif_taxon_key=999004,
        image_url=long_url,
        image_source_url=long_url,
    )
    sp.refresh_from_db()
    assert sp.image_url == long_url
    assert sp.image_source_url == long_url
