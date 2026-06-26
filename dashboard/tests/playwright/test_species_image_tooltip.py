import datetime
import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from playwright.sync_api import Page, expect

from dashboard.models import (
    BasisOfRecord, DataImport, Dataset, Observation, Species,
)

# A minimal 1x1 transparent PNG (67 bytes) used to serve the stub image URL
# so that the <img> does not trigger its onerror handler during tests.
_TINY_PNG = bytes([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
    0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41,
    0x54, 0x78, 0x9c, 0x62, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00,
    0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
    0x42, 0x60, 0x82,
])


@pytest.mark.django_db(transaction=True)
def test_species_tooltip_shows_image(page: Page, live_server):
    di = DataImport.objects.create(start=timezone.now())
    sp = Species.objects.create(
        name="Vulpes vulpes", gbif_taxon_key=999040,
        image_url="https://example.org/fox.jpg",
        image_attribution="Jane Doe", image_license="CC BY-SA 4.0",
        image_source_type=Species.ImageSourceType.WIKIPEDIA,
    )
    Observation.objects.create(
        gbif_id=42, occurrence_id="42", species=sp,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=Dataset.objects.create(name="D", gbif_dataset_key="k"),
        location=Point(5.09, 50.48, srid=4326),
        basis_of_record=BasisOfRecord.objects.create(name="HUMAN_OBSERVATION"),
    )

    # Intercept the stub image URL so the browser receives a real image and the
    # onerror handler does not hide the <img>.
    page.route(
        "https://example.org/fox.jpg",
        lambda route: route.fulfill(
            status=200, content_type="image/png", body=_TINY_PNG
        ),
    )

    # Navigate to index with status=all so the observation is visible
    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    # Switch to table view where SpeciesName renders
    page.get_by_role("tab", name="Table").click()
    page.wait_for_load_state("networkidle")
    # Find the species-name element and hover it
    name = page.locator(".species-name", has_text="Vulpes vulpes").first
    name.hover()
    # PrimeVue renders the tooltip with our injected <img>.
    expect(page.locator('.p-tooltip img[src="https://example.org/fox.jpg"]')
           ).to_be_visible()
