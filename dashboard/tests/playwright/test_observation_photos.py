"""Observation photos (riparias/gbif-alert#430).

- The detail panel lists an observation's photos, credited, each linking to its
  source, capped with a link to GBIF for the rest.
- A thumbnail that fails to load is dropped rather than shown broken.
- A camera icon in its own table column (and in the mobile card) marks
  observations with photos; hovering it shows the observation's photo.
- Hovering a species name always shows the generic species image, labelled as
  such - in the table and in the detail panel alike.

Thumbnails come from GBIF's image cache; every test routes it to a local PNG so
no request leaves the machine.
"""

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
    ObservationImage,
    Species,
)
from dashboard.tests.playwright.helpers import solid_png

GBIF_IMAGE_CACHE = "https://api.gbif.org/v1/image/cache/**"
_PNG = solid_png(200, 150)


def _serve_png(route):
    route.fulfill(status=200, content_type="image/png", body=_PNG)


def _observation(species: Species | None = None) -> Observation:
    di = DataImport.objects.create(start=timezone.now())
    return Observation.objects.create(
        gbif_id="6320328664",
        occurrence_id="occ-1",
        species=species
        or Species.objects.create(name="Vulpes vulpes", gbif_taxon_key=999040),
        date=datetime.date.today(),
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(name="D", gbif_dataset_key="k"),
        location=Point(5.09, 50.48, srid=4326),
        basis_of_record=BasisOfRecord.objects.create(name="HUMAN_OBSERVATION"),
    )


def _add_images(obs: Observation, n: int, **fields) -> list[ObservationImage]:
    return [
        ObservationImage.objects.create(
            observation=obs, identifier=f"https://example.org/{i}.jpg", **fields
        )
        for i in range(n)
    ]


@pytest.mark.django_db(transaction=True)
def test_detail_panel_shows_credited_photos(page: Page, live_server):
    obs = _observation()
    ObservationImage.objects.create(
        observation=obs,
        identifier="https://example.org/a.jpg",
        references="https://www.inaturalist.org/photos/589310386",
        attribution="Marleen 61",
        license="http://creativecommons.org/licenses/by-nc/4.0/",
    )
    # Pl@ntNet puts a credit, not a URL, in dcterms:references.
    ObservationImage.objects.create(
        observation=obs,
        identifier="https://example.org/b.jpg",
        references="Veronique Geijsels (cc-by-sa)",
    )
    page.route(GBIF_IMAGE_CACHE, _serve_png)

    page.goto(live_server.url + f"/?status=all&obs={obs.stable_id}")

    photos = page.locator(".observation-photos")
    expect(photos).to_contain_text("Photos of this observation")
    links = photos.locator("li a")
    expect(links).to_have_count(2)
    expect(links.nth(0)).to_have_attribute(
        "href", "https://www.inaturalist.org/photos/589310386"
    )
    expect(links.nth(1)).to_have_attribute("href", "https://example.org/b.jpg")
    expect(photos.locator("li").nth(0)).to_contain_text("Marleen 61")
    expect(photos.locator("li").nth(0)).to_contain_text("CC BY-NC 4.0")


@pytest.mark.django_db(transaction=True)
def test_detail_panel_caps_photos_and_links_to_gbif(page: Page, live_server):
    """Camera-trap observations carry hundreds of frames: show 12, link the rest."""
    obs = _observation()
    _add_images(obs, 15)
    page.route(GBIF_IMAGE_CACHE, _serve_png)

    page.goto(live_server.url + f"/?status=all&obs={obs.stable_id}")

    photos = page.locator(".observation-photos")
    expect(photos.locator("img")).to_have_count(12)
    more = photos.get_by_role("link", name="View all 15 photos on GBIF")
    expect(more).to_have_attribute("href", "https://www.gbif.org/occurrence/6320328664")


@pytest.mark.django_db(transaction=True)
def test_broken_thumbnails_are_dropped(page: Page, live_server):
    """GBIF cannot serve every image (xeno-canto sonograms 404): drop those, and
    the whole card when none is left."""
    obs = _observation()
    broken, working = _add_images(obs, 2)
    page.route(
        GBIF_IMAGE_CACHE,
        lambda route: (
            route.fulfill(status=404)
            if route.request.url == broken.gbif_thumbnail_url
            else _serve_png(route)
        ),
    )

    page.goto(live_server.url + f"/?status=all&obs={obs.stable_id}")

    photos = page.locator(".observation-photos")
    expect(photos.locator("img")).to_have_count(1)
    expect(photos.locator("img")).to_have_attribute("src", working.gbif_thumbnail_url)


@pytest.mark.django_db(transaction=True)
def test_card_hidden_when_no_thumbnail_loads(page: Page, live_server):
    obs = _observation()
    _add_images(obs, 2)
    page.route(GBIF_IMAGE_CACHE, lambda route: route.fulfill(status=404))

    page.goto(live_server.url + f"/?status=all&obs={obs.stable_id}")

    drawer = page.locator('[data-pc-name="drawer"]')
    expect(drawer.get_by_text("Vulpes vulpes").first).to_be_visible()
    expect(page.locator(".observation-photos")).to_have_count(0)


def _fox_with_photo() -> tuple[Observation, ObservationImage]:
    """An observation with one photo, of a species that has a generic image."""
    species = Species.objects.create(
        name="Vulpes vulpes",
        gbif_taxon_key=999040,
        image_url="https://example.org/generic-fox.jpg",
    )
    obs = _observation(species)
    (image,) = _add_images(obs, 1, attribution="Marleen 61")
    return obs, image


def _serve_all_images(page: Page) -> None:
    page.route(GBIF_IMAGE_CACHE, _serve_png)
    page.route("https://example.org/generic-fox.jpg", _serve_png)


GENERIC_IMG = 'img[src="https://example.org/generic-fox.jpg"]'


@pytest.mark.django_db(transaction=True)
def test_camera_column_shows_the_observation_photo(page: Page, live_server):
    """The camera has its own column; hovering it shows the observation's photo."""
    obs, image = _fox_with_photo()
    _serve_all_images(page)

    page.goto(live_server.url + "/?status=all")
    page.get_by_role("tab", name="Table").click()
    row = page.locator(".p-datatable tbody tr").first
    expect(row.locator(".species-name .pi-camera")).to_have_count(0)
    camera = row.locator(".observation-photo-icon")
    expect(camera).to_be_visible()
    camera.hover()

    tooltip = page.locator(".p-tooltip")
    expect(tooltip.locator(f'img[src="{image.gbif_thumbnail_url}"]')).to_be_visible()
    expect(tooltip).to_contain_text("Photo of this observation")
    expect(tooltip).to_contain_text("Marleen 61")
    expect(tooltip.locator(GENERIC_IMG)).to_have_count(0)


@pytest.mark.django_db(transaction=True)
def test_table_species_name_shows_the_generic_image(page: Page, live_server):
    """Even when the observation has a photo, the species tooltip shows the
    species' generic image, and says it is generic."""
    obs, image = _fox_with_photo()
    _serve_all_images(page)

    page.goto(live_server.url + "/?status=all")
    page.get_by_role("tab", name="Table").click()
    page.locator(".species-name", has_text="Vulpes vulpes").first.hover()

    tooltip = page.locator(".p-tooltip")
    expect(tooltip.locator(GENERIC_IMG)).to_be_visible()
    expect(tooltip).to_contain_text("Generic image of this species")
    expect(tooltip.locator(f'img[src="{image.gbif_thumbnail_url}"]')).to_have_count(0)


@pytest.mark.django_db(transaction=True)
def test_drawer_species_name_shows_the_generic_image(page: Page, live_server):
    """In the detail panel the photos are in their own card: the species name
    shows only the generic image, and carries no camera icon."""
    obs, image = _fox_with_photo()
    _serve_all_images(page)

    page.goto(live_server.url + f"/?status=all&obs={obs.stable_id}")
    drawer = page.locator('[data-pc-name="drawer"]')
    expect(drawer.locator(".observation-photos img")).to_be_visible()
    expect(drawer.locator(".species-name .pi-camera")).to_have_count(0)
    drawer.locator(".species-name").first.hover()

    tooltip = page.locator(".p-tooltip")
    expect(tooltip.locator(GENERIC_IMG)).to_be_visible()
    expect(tooltip).to_contain_text("Generic image of this species")
    expect(tooltip.locator(f'img[src="{image.gbif_thumbnail_url}"]')).to_have_count(0)


@pytest.mark.django_db(transaction=True)
def test_mobile_card_shows_the_camera(page: Page, live_server):
    _fox_with_photo()
    _serve_all_images(page)
    page.set_viewport_size({"width": 375, "height": 812})

    # On a phone the list of cards is the initial view.
    page.goto(live_server.url + "/?status=all")

    expect(page.locator(".obs-card .observation-photo-icon").first).to_be_visible()
