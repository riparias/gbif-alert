"""Playwright end-to-end tests for the Vue navbar (Phase 1).

These tests verify the rendered behaviour of NavBar.vue - that the right links
are visible for different user states, that the admin panel is gated to
superusers, and that the unseen-observations red dot appears when expected.

The server-side data that feeds the navbar (nav_config_json) is tested
separately in dashboard/tests/views/test_pages.py::NavConfigJsonTests.
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
    ObservationUnseen,
    Species,
)
from dashboard.tests.playwright.helpers import login


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_observation() -> Observation:
    """Create the minimal DB state needed for one observation to exist."""
    di = DataImport.objects.create(start=timezone.now())
    return Observation.objects.create(
        gbif_id=1,
        occurrence_id="1",
        species=Species.objects.create(name="Test species", gbif_taxon_key=1),
        date=datetime.date.today(),
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="test-dataset-key"
        ),
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=BasisOfRecord.objects.create(name="HUMAN_OBSERVATION"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_navbar_renders(page: Page, live_server):
    """The PrimeVue Menubar mounts and is visible on the homepage."""
    page.goto(live_server.url + "/")
    expect(page.locator('[data-pc-name="menubar"]')).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_anonymous_shows_signin_hides_my_alerts(page: Page, live_server):
    """Anonymous visitors see 'Sign in' but not the 'My alerts' nav item."""
    page.goto(live_server.url + "/")
    expect(page.get_by_role("link", name="Sign in")).to_be_visible()
    expect(page.get_by_role("menuitem", name="My alerts")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_authenticated_shows_my_alerts(page: Page, live_server):
    """Authenticated users see 'My alerts' in the menubar."""
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")
    expect(page.get_by_role("menuitem", name="My alerts")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_regular_user_no_admin_panel(page: Page, live_server):
    """The admin panel link is absent from the user dropdown for regular users."""
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")

    # Open the user dropdown to confirm the menu rendered without admin panel.
    page.get_by_role("button", name="testuser").click()
    # "Sign out" confirms the menu is open.
    expect(page.get_by_role("menuitem", name="Sign out")).to_be_visible()
    expect(page.get_by_role("menuitem", name="Admin panel")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_superuser_sees_admin_panel(page: Page, live_server):
    """Superusers see the admin panel link in their user dropdown."""
    User = get_user_model()
    User.objects.create_superuser(
        username="admin", password="adminpass123", email="admin@example.com"
    )
    login(page, live_server.url, "admin", "adminpass123")
    page.goto(live_server.url + "/")

    page.get_by_role("button", name="admin").click()
    expect(page.get_by_role("menuitem", name="Admin panel")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_red_dot_with_unseen_observations(page: Page, live_server):
    """A red dot appears inside the 'My alerts' menubar item when the user
    has an alert with unseen observations.

    ObservationUnseen records must be created explicitly - they are not produced
    automatically when creating Observations directly in tests (only the import
    pipeline calls create_unseen_observations()).
    """
    User = get_user_model()
    user = User.objects.create_user(username="testuser", password="testpass123")
    Alert.objects.create(user=user, email_notifications_frequency="D")
    obs = _create_observation()
    ObservationUnseen.objects.create(observation=obs, user=user)

    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")

    # Red dot inside the "My alerts" menubar item.
    my_alerts_item = page.get_by_role("menuitem", name="My alerts")
    expect(my_alerts_item.locator(".gbif-nav-dot")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_no_observations_dot_without_unseen_observations(page: Page, live_server):
    """No red dot is shown on 'My alerts' when the user has no unseen observations.

    Note: the news dot (.gbif-nav-dot on the 'What's new' item) is intentionally
    ignored here - it is controlled by has_unseen_news and is always shown for
    fresh users whose last_visit_news_page is None. This test only checks the
    observations dot on the 'My alerts' menubar item.
    """
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")

    my_alerts_item = page.get_by_role("menuitem", name="My alerts")
    expect(my_alerts_item.locator(".gbif-nav-dot")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_regular_user_cannot_access_admin_directly(page: Page, live_server):
    """A regular user who navigates directly to /admin is denied access."""
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/admin/")
    page.wait_for_load_state("networkidle")

    # Django redirects to admin login and shows an "not authorized" message.
    expect(page).to_have_url(live_server.url + "/admin/login/?next=/admin/")
    expect(
        page.get_by_text("are not authorized to access this page", exact=False)
    ).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_superuser_can_access_admin_directly(page: Page, live_server):
    """A superuser who navigates directly to /admin lands on the admin dashboard."""
    User = get_user_model()
    User.objects.create_superuser(
        username="admin", password="adminpass123", email="admin@example.com"
    )
    login(page, live_server.url, "admin", "adminpass123")
    page.goto(live_server.url + "/admin/")
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/admin/")
    expect(page).to_have_title("Site administration | Django site admin")
