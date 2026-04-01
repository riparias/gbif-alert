"""Playwright end-to-end tests for the index page (Phase 2, step 2.16).

Tests cover:
- Index page renders with the filter panel and observation counter
- Observation counter (singular and plural forms)
- Empty state shown when no results match
- Species filter narrows the observation count
- Dataset filter narrows the observation count
- Switching to table view: species name, verified/unverified badges, seen column
- Clicking a table row opens the observation detail drawer (?obs= in URL)
- Direct deep-link URL (?obs=<stableId>) opens the drawer on load
- Filter state in the URL is preserved when the drawer is opened and closed
  (this is the key behaviour solved by the Vue Router + Pinia architecture -
  the old frontend would lose filter state on navigation)
- Authenticated user sees unseen observations by default
- Smart status fallback: authenticated user with no unseen observations sees all
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observation(
    *,
    gbif_id: int,
    occurrence_id: str,
    species: Species,
    basis: BasisOfRecord,
    dataset: Dataset | None = None,
    verified: bool = False,
    municipality: str = "",
) -> Observation:
    di = DataImport.objects.create(start=timezone.now())
    if dataset is None:
        dataset = Dataset.objects.create(
            name=f"Dataset {gbif_id}",
            gbif_dataset_key=f"key-{gbif_id}",
        )
    return Observation.objects.create(
        gbif_id=gbif_id,
        occurrence_id=occurrence_id,
        species=species,
        date=datetime.date.today(),
        data_import=di,
        initial_data_import=di,
        source_dataset=dataset,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis,
        verified=verified,
        municipality=municipality,
    )


def _login(page: Page, base_url: str, username: str, password: str) -> None:
    """Log in via the sign-in form and wait for the redirect to complete."""
    page.goto(base_url + "/accounts/signin/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("#gbif-alert-signin-button")
    page.wait_for_load_state("networkidle")


def _switch_to_table_view(page: Page) -> None:
    page.get_by_role("tab", name="Table").click()
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Rendering and counter
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_index_page_renders(page: Page, live_server):
    """The index page loads: filter panel and observation counter are visible."""
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Filters", exact=True)).to_be_visible()
    expect(page.locator(".observation-counter")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_counter_plural(page: Page, live_server):
    """The counter shows the plural form for multiple observations."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)
    _make_observation(gbif_id=2, occurrence_id="2", species=sp, basis=basis)

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("2 matching observations")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_counter_singular(page: Page, live_server):
    """The counter shows the singular form for exactly one observation."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("One matching observation")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_empty_state_shown_when_no_results(page: Page, live_server):
    """When no observations match the filter the empty-state UI is shown."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp1 = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    sp2 = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp1, basis=basis)

    # Filter to sp2 which has no observations
    page.goto(live_server.url + f"/?status=all&speciesIds={sp2.pk}")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("No matching results found.")).to_be_visible()
    expect(
        page.get_by_text("Try adjusting or clearing the filters above.")
    ).to_be_visible()
    # Histogram and map/table tabs are hidden when there are no results
    expect(page.get_by_role("tab", name="Table")).not_to_be_visible()


# ---------------------------------------------------------------------------
# URL-driven filters
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_species_filter_narrows_results(page: Page, live_server):
    """Adding a speciesIds filter to the URL reduces the observation count."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp1 = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    sp2 = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp1, basis=basis)
    _make_observation(gbif_id=2, occurrence_id="2", species=sp1, basis=basis)
    _make_observation(gbif_id=3, occurrence_id="3", species=sp2, basis=basis)

    # Unfiltered: 3 observations
    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("3 matching observations")).to_be_visible()

    # Filtered to sp1: 2 observations
    page.goto(live_server.url + f"/?status=all&speciesIds={sp1.pk}")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("2 matching observations")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_dataset_filter_narrows_results(page: Page, live_server):
    """Adding a datasetsIds filter to the URL reduces the observation count."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    ds1 = Dataset.objects.create(name="Dataset A", gbif_dataset_key="key-a")
    ds2 = Dataset.objects.create(name="Dataset B", gbif_dataset_key="key-b")
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis, dataset=ds1)
    _make_observation(gbif_id=2, occurrence_id="2", species=sp, basis=basis, dataset=ds1)
    _make_observation(gbif_id=3, occurrence_id="3", species=sp, basis=basis, dataset=ds2)

    # Filtered to ds1: 2 observations
    page.goto(live_server.url + f"/?status=all&datasetsIds={ds1.pk}")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("2 matching observations")).to_be_visible()


# ---------------------------------------------------------------------------
# Table view
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_table_view_shows_species_name(page: Page, live_server):
    """Switching to the Table tab displays the observation's scientific name."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    expect(page.get_by_text("Procambarus fallax")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_table_shows_verified_badge(page: Page, live_server):
    """A verified observation shows a green 'Verified' badge in the table."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(
        gbif_id=1, occurrence_id="1", species=sp, basis=basis, verified=True
    )

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    badge = page.locator(".badge-success")
    expect(badge).to_be_visible()
    expect(badge).to_have_text("Verified")


@pytest.mark.django_db(transaction=True)
def test_table_shows_unverified_badge(page: Page, live_server):
    """An unverified observation shows a red 'Unverified' badge in the table."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(
        gbif_id=1, occurrence_id="1", species=sp, basis=basis, verified=False
    )

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    badge = page.locator(".badge-danger")
    expect(badge).to_be_visible()
    expect(badge).to_have_text("Unverified")


@pytest.mark.django_db(transaction=True)
def test_seen_column_shown_for_authenticated_user(page: Page, live_server):
    """The 'Seen' column appears in the table for authenticated users who have
    at least one observation with a seen/unseen record."""
    User = get_user_model()
    user = User.objects.create_user(username="testuser", password="testpass123")
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    obs = _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)
    ObservationUnseen.objects.create(observation=obs, user=user)

    _login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    expect(page.get_by_role("columnheader", name="Seen")).to_be_visible()


# ---------------------------------------------------------------------------
# Observation drawer
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_table_row_click_opens_observation_drawer(page: Page, live_server):
    """Clicking a DataTable row adds ?obs=<stableId> to the URL and opens the drawer."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    obs = _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    page.locator("tbody tr").first.click()
    page.wait_for_url(re.compile(r"obs="))

    drawer = page.locator('[data-pc-name="drawer"]')
    expect(drawer).to_be_visible()
    expect(drawer.get_by_text(obs.species.name).first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_deep_link_url_opens_drawer_on_load(page: Page, live_server):
    """Navigating directly to /?obs=<stableId> opens the drawer without interaction."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    obs = _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + f"/?status=all&obs={obs.stable_id}")
    page.wait_for_load_state("networkidle")

    drawer = page.locator('[data-pc-name="drawer"]')
    expect(drawer).to_be_visible()
    expect(drawer.get_by_text(obs.species.name).first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_filter_state_preserved_when_drawer_closed(page: Page, live_server):
    """Closing the observation drawer removes ?obs= but keeps other filter params.

    This is the key behaviour that motivated the Vue Router migration: the old
    frontend lost all filter state when navigating to observation details and
    pressing the browser back button. The new frontend encodes all filters in
    the URL, so closing the drawer simply removes the ?obs= param while the
    rest of the query string stays intact.
    """
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    obs = _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    # Navigate with both a species filter and the drawer open
    page.goto(
        live_server.url + f"/?status=all&speciesIds={sp.pk}&obs={obs.stable_id}"
    )
    page.wait_for_load_state("networkidle")
    expect(page.locator('[data-pc-name="drawer"]')).to_be_visible()

    # Close the drawer via the X button
    page.get_by_role("button", name="Close").click()
    page.wait_for_load_state("networkidle")

    # ?obs= is gone; speciesIds filter is still present
    sp_pk = sp.pk
    expect(page).not_to_have_url(re.compile(r"obs="))
    expect(page).to_have_url(re.compile(rf"speciesIds={sp_pk}"))


# ---------------------------------------------------------------------------
# Authentication and status filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_authenticated_user_sees_unseen_by_default(page: Page, live_server):
    """An authenticated user with unseen observations sees only those by default.

    The Pinia filters store initialises status='unseen'. If the user has unseen
    observations the smart-default code does not override it, so only the unseen
    subset is shown.
    """
    User = get_user_model()
    user = User.objects.create_user(username="testuser", password="testpass123")
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)

    obs1 = _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)
    obs2 = _make_observation(gbif_id=2, occurrence_id="2", species=sp, basis=basis)
    _make_observation(gbif_id=3, occurrence_id="3", species=sp, basis=basis)

    # Only 2 of the 3 observations are unseen for this user
    ObservationUnseen.objects.create(observation=obs1, user=user)
    ObservationUnseen.objects.create(observation=obs2, user=user)

    _login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("2 matching observations")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_smart_status_default_falls_back_to_all(page: Page, live_server):
    """When an authenticated user has no unseen observations the status filter
    falls back silently from 'unseen' to 'all', showing all observations.

    The smart-default logic in IndexPage.vue detects 0 results with the initial
    'unseen' filter and re-fetches with status=null (all) so the user is never
    greeted by an empty page.
    """
    User = get_user_model()
    User.objects.create_user(username="testuser", password="testpass123")
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)
    _make_observation(gbif_id=2, occurrence_id="2", species=sp, basis=basis)
    # No ObservationUnseen records - user has nothing unseen

    _login(page, live_server.url, "testuser", "testpass123")
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")

    # Falls back to 'all': both observations are shown
    expect(page.get_by_text("2 matching observations")).to_be_visible()
