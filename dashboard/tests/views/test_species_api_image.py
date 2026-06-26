import pytest
from dashboard.models import Species


@pytest.mark.django_db
def test_species_endpoint_returns_image_fields(client):
    Species.objects.create(
        name="Testus specius",
        gbif_taxon_key=999010,
        image_url="https://example.org/x.jpg",
        image_source_url="https://en.wikipedia.org/wiki/Testus",
        image_attribution="Jane Doe",
        image_license="CC BY-SA 4.0",
        image_source_type=Species.ImageSourceType.WIKIPEDIA,
    )
    resp = client.get("/api/v2/species/")
    assert resp.status_code == 200
    entry = next(e for e in resp.json() if e["gbifTaxonKey"] == 999010)
    assert entry["imageUrl"] == "https://example.org/x.jpg"
    assert entry["imageSourceUrl"] == "https://en.wikipedia.org/wiki/Testus"
    assert entry["imageAttribution"] == "Jane Doe"
    assert entry["imageLicense"] == "CC BY-SA 4.0"
    assert entry["imageSourceType"] == "wikipedia"
