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
    """Log in via the Vue sign-in page and wait until redirected to /."""
    page.goto(base_url + "/accounts/signin/")
    page.wait_for_load_state("networkidle")
    page.locator("#signin-username").fill(username)
    page.locator("#signin-password").fill(password)
    with page.expect_navigation():
        page.get_by_role("button", name="Sign in").click()
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
def test_area_card_shows_tags(page: Page, live_server):
    """Tags stored on an area are displayed as chips on its card."""
    User = get_user_model()
    user = User.objects.create_user(username="t1", password="pass", email="t1@t.com")
    area = _make_area(user, "Tagged area")
    area.tags.add("woodland", "protected")

    _login(page, live_server.url, "t1", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("woodland", exact=True)).to_be_visible()
    expect(page.get_by_text("protected", exact=True)).to_be_visible()


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

    page.get_by_role("button", name="Delete").click()
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

    page.get_by_role("button", name="Delete").click()
    page.get_by_role("button", name="Cancel").click()

    expect(page.locator(".area-card").filter(has_text="Area to keep")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_delete_area_with_alert_shows_error(page: Page, live_server):
    """Trying to delete an area referenced by an alert shows an error toast."""
    User = get_user_model()
    user = User.objects.create_user(username="a8", password="pass", email="a8@t.com")
    area = _make_area(user, "Area with alert")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    alert = Alert.objects.create(
        name="My alert", user=user, email_notifications_frequency="N"
    )
    alert.species.add(sp)
    alert.areas.add(area)

    _login(page, live_server.url, "a8", "pass")
    page.goto(live_server.url + "/my-custom-areas")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete").click()
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    # Error toast must be visible
    expect(page.locator(".p-toast")).to_be_visible()
    expect(page.locator(".p-toast")).to_contain_text("Cannot delete area", ignore_case=True)

    # Area is still in the list
    expect(page.locator(".area-card").filter(has_text="Area with alert")).to_be_visible()
    assert Area.objects.filter(pk=area.pk).exists()


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

    page.get_by_role("button", name="Add area").click()
    page.get_by_text("Upload file").click()

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

    page.get_by_role("button", name="Add area").click()
    page.get_by_text("Upload file").click()

    page.locator("#area-name").fill("Bad area")
    page.locator("input[type=file]").set_input_files(POINT_GPKG)
    page.get_by_role("button", name="Upload").click()
    page.wait_for_load_state("networkidle")

    # Dialog stays open and shows an error
    expect(page.locator("[data-testid='area-upload-error']")).to_be_visible()


# ---------------------------------------------------------------------------
# /my-custom-areas/new - editor create mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_editor_create_mode_loads(page: Page, live_server):
    """Create-mode editor page renders with correct elements."""
    User = get_user_model()
    User.objects.create_user(username="e1", password="pass", email="e1@t.com")

    _login(page, live_server.url, "e1", "pass")
    page.goto(live_server.url + "/my-custom-areas/new")
    page.wait_for_load_state("networkidle")

    expect(page.locator("#editor-area-name")).to_be_visible()
    expect(page.get_by_role("button", name="Draw polygon")).to_be_visible()
    expect(page.get_by_role("button", name="Edit vertices")).to_be_visible()
    expect(page.get_by_role("button", name="Delete polygon")).to_be_visible()
    expect(page.get_by_role("button", name="Save")).to_be_visible()
    expect(page.get_by_role("button", name="Cancel")).to_be_visible()
    # Save is disabled - no name or polygon yet
    expect(page.get_by_role("button", name="Save")).to_be_disabled()
    # "Delete area" button must NOT appear in create mode
    expect(page.get_by_role("button", name="Delete area")).not_to_be_attached()


@pytest.mark.django_db(transaction=True)
def test_editor_create_mode_requires_login(page: Page, live_server):
    """Anonymous user is redirected away from the create editor."""
    page.goto(live_server.url + "/my-custom-areas/new")
    page.wait_for_load_state("networkidle")
    expect(page).not_to_have_url(live_server.url + "/my-custom-areas/new")


# ---------------------------------------------------------------------------
# /my-custom-areas/:id/edit - editor edit mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_editor_edit_mode_prefills_name(page: Page, live_server):
    """Edit-mode editor pre-fills the area name input."""
    User = get_user_model()
    user = User.objects.create_user(username="e2", password="pass", email="e2@t.com")
    area = _make_area(user, "Prefilled area")

    _login(page, live_server.url, "e2", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    expect(page.locator("#editor-area-name")).to_have_value("Prefilled area")
    expect(page.get_by_role("button", name="Delete area")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_editor_edit_mode_rename_and_save(page: Page, live_server):
    """Renaming an area via the editor persists to the database."""
    User = get_user_model()
    user = User.objects.create_user(username="e3", password="pass", email="e3@t.com")
    area = _make_area(user, "Old name")

    _login(page, live_server.url, "e3", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    page.locator("#editor-area-name").fill("New name")
    page.get_by_role("button", name="Save").click()
    page.wait_for_load_state("networkidle")

    # Should redirect back to the list page
    expect(page).to_have_url(live_server.url + "/my-custom-areas")

    area.refresh_from_db()
    assert area.name == "New name"


@pytest.mark.django_db(transaction=True)
def test_editor_delete_area_button(page: Page, live_server):
    """Delete area button in the editor removes the area and redirects to the list."""
    User = get_user_model()
    user = User.objects.create_user(username="e4", password="pass", email="e4@t.com")
    area = _make_area(user, "Area to delete from editor")

    _login(page, live_server.url, "e4", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete area").click()
    # PrimeVue ConfirmDialog - click the accept button
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/my-custom-areas")
    assert not Area.objects.filter(pk=area.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_editor_cancel_returns_to_list(page: Page, live_server):
    """Clicking Cancel in the editor navigates back to the area list."""
    User = get_user_model()
    user = User.objects.create_user(username="e5", password="pass", email="e5@t.com")
    area = _make_area(user, "Stay intact")

    _login(page, live_server.url, "e5", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Cancel").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/my-custom-areas")
