"""Playwright E2E tests for Phase 4 user area pages.

Test data is created per-test (no shared state) using @pytest.mark.django_db(transaction=True).
"""

from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from playwright.sync_api import Page, expect

from dashboard.models import Alert, Area, Species


SAMPLE_DATA_DIR = Path(__file__).parent.parent / "various" / "sample_data"
POLYGON_GPKG = str(SAMPLE_DATA_DIR / "polygon_4326.gpkg")
POINT_GPKG = str(SAMPLE_DATA_DIR / "point.gpkg")

SIMPLE_POLYGON = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)), srid=4326))


def _login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(base_url + "/accounts/signin/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("#gbif-alert-signin-button")
    page.wait_for_load_state("networkidle")


def _make_area(user, name: str) -> Area:
    return Area.objects.create(name=name, owner=user, mpoly=SIMPLE_POLYGON)


# ---------------------------------------------------------------------------
# /my-custom-areas - list, empty state, login redirect
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_my_areas_page_shows_area_list(page: Page, live_server):
    """Authenticated user sees their area names on /my-custom-areas."""
    User = get_user_model()
    user = User.objects.create_user(username="a1", password="pass", email="a1@t.com")
    _make_area(user, "My polygon area")

    _login(page, live_server.url, "a1", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("My polygon area")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_my_areas_empty_state(page: Page, live_server):
    """User with no areas sees an empty state message."""
    User = get_user_model()
    User.objects.create_user(username="a2", password="pass", email="a2@t.com")

    _login(page, live_server.url, "a2", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    expect(
        page.get_by_text("don't have any custom areas", exact=False)
    ).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_my_areas_page_requires_login(page: Page, live_server):
    """Anonymous user is redirected away from /my-custom-areas."""
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")
    expect(page).not_to_have_url(live_server.url + "/my-custom-areas")


# ---------------------------------------------------------------------------
# /my-custom-areas - delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_delete_area_confirmed(page: Page, live_server):
    """Confirming delete removes the area from the list."""
    User = get_user_model()
    user = User.objects.create_user(username="a4", password="pass", email="a4@t.com")
    area = _make_area(user, "Area to delete")

    _login(page, live_server.url, "a4", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete this area").click()
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator(".area-card").filter(has_text="Area to delete")).not_to_be_visible()
    assert not Area.objects.filter(pk=area.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_delete_area_cancelled(page: Page, live_server):
    """Cancelling the delete dialog leaves the area intact."""
    User = get_user_model()
    user = User.objects.create_user(username="a5", password="pass", email="a5@t.com")
    _make_area(user, "Area to keep")

    _login(page, live_server.url, "a5", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete this area").click()
    page.get_by_role("button", name="Cancel").click()

    expect(page.locator(".area-card").filter(has_text="Area to keep")).to_be_visible()


# ---------------------------------------------------------------------------
# /my-custom-areas - create
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_create_area_succeeds(page: Page, live_server):
    """Uploading a valid GeoPackage creates a new area and it appears in the list."""
    User = get_user_model()
    User.objects.create_user(username="a6", password="pass", email="a6@t.com")

    _login(page, live_server.url, "a6", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="New area").click()

    # Fill the upload form inside the dialog
    page.locator("#area-name").fill("My uploaded area")
    page.locator("input[type=file]").set_input_files(POLYGON_GPKG)
    page.get_by_role("button", name="Upload").click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("My uploaded area")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_create_area_invalid_file_shows_error(page: Page, live_server):
    """Uploading a GeoPackage with wrong geometry type shows an inline error."""
    User = get_user_model()
    User.objects.create_user(username="a7", password="pass", email="a7@t.com")

    _login(page, live_server.url, "a7", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="New area").click()

    page.locator("#area-name").fill("Bad area")
    page.locator("input[type=file]").set_input_files(POINT_GPKG)
    page.get_by_role("button", name="Upload").click()
    page.wait_for_load_state("networkidle")

    # Dialog stays open and shows an error
    expect(page.locator("[data-testid='area-upload-error']")).to_be_visible()
