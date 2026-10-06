import datetime

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from playwright.sync_api import Page, expect

from dashboard.models import (
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    Species,
)
from dashboard.tests.playwright.helpers import solid_png


# A wide image so the tooltip image is rendered at a real, non-trivial size.
_WIDE_PNG = solid_png(400, 260)


@pytest.mark.django_db(transaction=True)
def test_species_tooltip_shows_image(page: Page, live_server):
    di = DataImport.objects.create(start=timezone.now())
    sp = Species.objects.create(
        name="Vulpes vulpes",
        gbif_taxon_key=999040,
        image_url="https://example.org/fox.jpg",
        image_attribution="Jane Doe",
        image_license="CC BY-SA 4.0",
        image_source_type=Species.ImageSourceType.WIKIPEDIA,
    )
    Observation.objects.create(
        gbif_id=42,
        occurrence_id="42",
        species=sp,
        date=datetime.date.today(),
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(name="D", gbif_dataset_key="k"),
        location=Point(5.09, 50.48, srid=4326),
        basis_of_record=BasisOfRecord.objects.create(name="HUMAN_OBSERVATION"),
    )

    # Intercept the stub image URL so the browser receives a real image and the
    # onerror handler does not hide the <img>.
    page.route(
        "https://example.org/fox.jpg",
        lambda route: route.fulfill(
            status=200, content_type="image/png", body=_WIDE_PNG
        ),
    )

    # Navigate to index with status=all so the observation is visible
    page.goto(live_server.url + "/?status=all")
    # Switch to table view where SpeciesName renders
    page.get_by_role("tab", name="Table").click()
    # Find the species-name element and hover it
    name = page.locator(".species-name", has_text="Vulpes vulpes").first
    name.hover()
    # PrimeVue renders the tooltip with our injected <img>.
    img = page.locator('.p-tooltip img[src="https://example.org/fox.jpg"]')
    expect(img).to_be_visible()
    # The observation has no photo of its own: say the image is generic.
    expect(page.locator(".p-tooltip")).to_contain_text("Generic image of this species")
    expect(name.locator(".pi-camera")).to_have_count(0)

    # Regression: the image must stay inside the tooltip's rounded box (it used
    # to overflow because the image was wider than PrimeVue's tooltip box).
    box = page.locator(".p-tooltip-text").first
    box_bb = box.bounding_box()
    img_bb = img.bounding_box()
    assert box_bb is not None and img_bb is not None
    assert img_bb["x"] >= box_bb["x"] - 1
    assert img_bb["x"] + img_bb["width"] <= box_bb["x"] + box_bb["width"] + 1
