import datetime
import struct
import zlib

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from playwright.sync_api import Page, expect

from dashboard.models import (
    BasisOfRecord, DataImport, Dataset, Observation, Species,
)


def _solid_png(width: int, height: int, rgb=(60, 140, 60)) -> bytes:
    """Build a valid solid-color RGB PNG of the given size (no Pillow needed).

    A genuinely wide image is required to exercise the tooltip's overflow
    handling - a 1x1 stub would never reach the CSS size limits.
    """
    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * width
    idat = zlib.compress(row * height)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


# A wide image so the tooltip image is rendered at a real, non-trivial size.
_WIDE_PNG = _solid_png(400, 260)


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
            status=200, content_type="image/png", body=_WIDE_PNG
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
    img = page.locator('.p-tooltip img[src="https://example.org/fox.jpg"]')
    expect(img).to_be_visible()

    # Regression: the image must stay inside the tooltip's rounded box (it used
    # to overflow because the image was wider than PrimeVue's tooltip box).
    box = page.locator(".p-tooltip-text").first
    box_bb = box.bounding_box()
    img_bb = img.bounding_box()
    assert box_bb is not None and img_bb is not None
    assert img_bb["x"] >= box_bb["x"] - 1
    assert img_bb["x"] + img_bb["width"] <= box_bb["x"] + box_bb["width"] + 1
