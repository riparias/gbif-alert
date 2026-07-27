"""The observations map fills the page down to the footer.

It used to be a flat 480px, which left roughly 490px of dead space below it on a
tall screen while the sidebar ran on past it.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone
from playwright.sync_api import Page, expect

from dashboard.models import (
    Alert,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    Species,
)
from dashboard.tests.playwright.helpers import login

MIN_MAP_HEIGHT_PX = 480

# How much of the viewport bottom the map's own bottom edge is allowed to miss.
# The map does not reach the very bottom: page padding and the footer sit below
# it, and the composable reserves room for both.
BOTTOM_SLACK_PX = 200


def _create_observation() -> Species:
    """One observation, so the page shows the map instead of its empty state.

    Returns its species, so an alert can be built to match it.
    """
    di = DataImport.objects.create(start=timezone.now())
    species = Species.objects.create(name="Test species", gbif_taxon_key=1)
    Observation.objects.create(
        gbif_id=1,
        occurrence_id="1",
        species=species,
        date=datetime.date.today(),
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="test-dataset-key"
        ),
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=BasisOfRecord.objects.create(name="HUMAN_OBSERVATION"),
    )
    return species


def _map_box(page: Page):
    """The rendered map's box, once it has been sized."""
    wrapper = page.locator(".base-map-wrapper")
    expect(wrapper).to_be_visible()
    box = wrapper.bounding_box()
    assert box is not None
    return box


@pytest.mark.django_db(transaction=True)
def test_map_grows_to_fill_a_tall_viewport(page: Page, live_server):
    """On a tall screen the map is far taller than the old fixed 480px."""
    _create_observation()
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.goto(live_server.url + "/")

    box = _map_box(page)
    assert box["height"] > MIN_MAP_HEIGHT_PX * 1.5, (
        f"map is only {box['height']}px tall on a 1400px viewport - it should "
        "fill the page rather than stay at its old fixed height"
    )
    # Its bottom edge lands near the bottom of the viewport, not far above it.
    assert box["y"] + box["height"] > 1400 - BOTTOM_SLACK_PX, (
        f"map ends at {box['y'] + box['height']}px on a 1400px viewport, "
        "leaving too much dead space below it"
    )


@pytest.mark.django_db(transaction=True)
def test_map_never_shrinks_below_its_old_fixed_height(page: Page, live_server):
    """A short viewport must not squeeze the map smaller than it always was.

    On a short screen there is no room to grow into - the map already runs past
    the fold - so the floor is what keeps this an improvement everywhere rather
    than a regression on laptops.
    """
    _create_observation()
    page.set_viewport_size({"width": 1280, "height": 700})
    page.goto(live_server.url + "/")

    box = _map_box(page)
    assert box["height"] >= MIN_MAP_HEIGHT_PX, (
        f"map shrank to {box['height']}px on a 700px viewport, below the "
        f"{MIN_MAP_HEIGHT_PX}px floor"
    )


@pytest.mark.django_db(transaction=True)
def test_map_resizes_when_the_window_does(page: Page, live_server):
    """The height is measured, so it has to be re-measured on resize."""
    _create_observation()
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.goto(live_server.url + "/")
    tall = _map_box(page)["height"]

    page.set_viewport_size({"width": 1280, "height": 700})
    page.wait_for_function(
        "h => document.querySelector('.base-map-wrapper').getBoundingClientRect().height < h",
        arg=tall,
    )
    assert _map_box(page)["height"] >= MIN_MAP_HEIGHT_PX


@pytest.mark.django_db(transaction=True)
def test_map_grows_on_the_alert_detail_page(page: Page, live_server):
    """The alert detail page shares the layout - and has a SHORT sidebar.

    This is why the height is viewport-based rather than aligned to the sidebar:
    following a short sidebar here would leave this map small, the opposite of
    the goal.
    """
    species = _create_observation()
    user = get_user_model().objects.create_user(
        username="alertuser", password="testpass123"
    )
    alert = Alert.objects.create(
        name="My alert", user=user, email_notifications_frequency="N"
    )
    alert.species.add(species)

    page.set_viewport_size({"width": 1280, "height": 1400})
    login(page, live_server.url, "alertuser", "testpass123")
    page.goto(live_server.url + f"/alert/{alert.pk}")

    box = _map_box(page)
    assert box["height"] > MIN_MAP_HEIGHT_PX * 1.5, (
        f"map is only {box['height']}px tall on the alert detail page - it "
        "should fill the page here too"
    )
