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
