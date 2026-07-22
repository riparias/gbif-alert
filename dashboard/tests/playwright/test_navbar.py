"""Playwright end-to-end tests for the Vue navbar (Phase 1).

These tests verify the rendered behaviour of NavBar.vue - that the right links
are visible for different user states, that the admin panel is gated to
superusers, and that the unseen-observations red dot appears when expected.

The server-side data that feeds the navbar (nav_config_json) is tested
separately in dashboard/tests/views/test_pages.py::NavConfigJsonTests.
"""

import datetime
import re

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
from page_fragments.models import NEWS_PAGE_IDENTIFIER, PageFragment


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


def _open_about_menu(page: Page) -> None:
    """Open the navbar's "About" submenu and return once its items are visible.

    The two about pages are grouped under a parent item, so they are not in the
    DOM until the submenu is opened.
    """
    page.get_by_role("menuitem", name="About", exact=True).click()
    expect(page.get_by_role("menuitem", name="About this site")).to_be_visible()


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
def test_navbar_no_observations_dot_without_unseen_observations(
    page: Page, live_server
):
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

    expect(page).to_have_url(live_server.url + "/admin/")
    expect(page).to_have_title("Site administration | Django site admin")


@pytest.mark.django_db(transaction=True)
def test_navbar_internal_link_navigates_without_reload(page: Page, live_server):
    """Clicking a main-menu item routes client-side instead of reloading.

    Regression test for the page "blink": the navbar links used to be plain
    anchors that triggered a full Django round-trip (re-bootstrapping the whole
    Vue app) on every click. They now navigate via Vue Router.

    We detect a full reload by stamping a marker on the window object before
    clicking - a real document navigation wipes the JS context and the marker
    disappears, while client-side routing preserves it.
    """
    page.goto(live_server.url + "/")
    expect(page.locator('[data-pc-name="menubar"]')).to_be_visible()

    # Stamp the current document so we can tell whether it survives the click.
    page.evaluate("window.__noReloadMarker = 'spa'")

    _open_about_menu(page)
    page.get_by_role("menuitem", name="About this site").click()

    # The route changed client-side...
    # Path-based: the filters store may append its own query string (e.g.
    # ?status=all) shortly after the route changes, which would race an
    # exact-URL assertion.
    expect(page).to_have_url(re.compile(r"/about-site(\?|$)"))
    # ...and the original document was never torn down (no full reload/blink).
    assert page.evaluate("window.__noReloadMarker") == "spa"


@pytest.mark.django_db(transaction=True)
def test_navbar_signout_logs_user_out(page: Page, live_server):
    """Clicking 'Sign out' ends the session and returns to the anonymous state.

    Regression test: sign-out used to be a plain GET anchor pointing at Django's
    LogoutView, which returns 405 Method Not Allowed under Django 5+, so the
    click silently failed to log the user out. It now POSTs to
    /api/v2/auth/signout/ and redirects home, leaving the navbar anonymous.
    """
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")

    page.get_by_role("button", name="testuser").click()
    page.get_by_role("menuitem", name="Sign out").click()

    # The session is gone: the navbar returns to its anonymous state.
    expect(page.get_by_role("link", name="Sign in")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_news_dot_clears_without_full_reload(page: Page, live_server):
    """The 'What's new' dot disappears as soon as the user visits the news page.

    Regression test: the dots used to be read from the nav-config JSON block
    injected at page load, which the SPA never refreshes - so the dot stayed lit
    while navigating client-side, until the next full page load.
    """
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    # update_or_create: a data migration may already have created the fragment.
    PageFragment.objects.update_or_create(
        identifier=NEWS_PAGE_IDENTIFIER, defaults={"content_en": "Something new"}
    )
    login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")

    news_item = page.get_by_role("menuitem", name="What's new")
    expect(news_item.locator(".gbif-nav-dot")).to_be_visible()

    page.evaluate("window.__noReloadMarker = 'spa'")
    news_item.click()

    # The dot is gone right away, and no full page load happened.
    expect(news_item.locator(".gbif-nav-dot")).not_to_be_visible()
    assert page.evaluate("window.__noReloadMarker") == "spa"

    # It stays gone after navigating client-side to another page.
    _open_about_menu(page)
    page.get_by_role("menuitem", name="About this site").click()
    # Path-based: the filters store may append its own query string (e.g.
    # ?status=all) shortly after the route changes, which would race an
    # exact-URL assertion.
    expect(page).to_have_url(re.compile(r"/about-site(\?|$)"))
    expect(news_item.locator(".gbif-nav-dot")).not_to_be_visible()
    assert page.evaluate("window.__noReloadMarker") == "spa"


@pytest.mark.django_db(transaction=True)
def test_navbar_about_pages_are_grouped_in_a_submenu(page: Page, live_server):
    """The two about pages sit under a single "About" navbar entry."""
    page.goto(live_server.url + "/")
    expect(page.locator('[data-pc-name="menubar"]')).to_be_visible()

    # Neither page is reachable at the top level...
    expect(page.get_by_role("menuitem", name="About this site")).to_have_count(0)
    expect(page.get_by_role("menuitem", name="About the data")).to_have_count(0)

    # ...they appear once the parent entry is opened.
    _open_about_menu(page)
    expect(page.get_by_role("menuitem", name="About the data")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_navbar_about_entry_is_active_on_a_child_page(page: Page, live_server):
    """The "About" entry is highlighted while the user is on one of its pages.

    The parent has no page of its own, so without this it would never show the
    active state that every other top-level entry gets.
    """
    page.goto(live_server.url + "/about-data")

    # The parent's own link, not the submenu child (which is also active here).
    about_link = page.get_by_role("menuitem", name="About", exact=True).locator(
        "a.gbif-nav-link:not(.gbif-nav-sub-link)"
    )
    expect(about_link).to_have_class(re.compile(r"\bgbif-nav-active\b"))


@pytest.mark.django_db(transaction=True)
def test_navbar_language_selector_shows_only_a_code_until_opened(
    page: Page, live_server
):
    """The language selector is collapsed to a globe + code to save navbar width.

    The full native names ("English", "Nederlands", ...) live in the overlay,
    which is widened independently of the collapsed trigger.

    Deliberately does not name a language: which ones are enabled is per-instance
    (ENABLED_LANGUAGES), so the assertions are on the shape of the labels - a
    two-letter code on the trigger, spelled-out names in the overlay.
    """
    page.goto(live_server.url + "/")

    selector = page.get_by_role("combobox", name="Language")
    # \s* because the globe icon element contributes whitespace to the text.
    expect(selector).to_have_text(re.compile(r"^\s*[A-Z]{2}\s*$"))

    selector.click()

    options = page.get_by_role("option")
    expect(options.first).to_be_visible()
    # The selector only renders at all when the instance enables 2+ languages.
    assert options.count() >= 2
    for label in options.all_inner_texts():
        assert len(label.strip()) > 2, f"overlay shows a collapsed label: {label!r}"
