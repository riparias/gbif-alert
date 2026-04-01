"""Playwright end-to-end tests for the index page (Phase 2, step 2.16).

Tests cover:
- Index page renders with the filter panel and observation counter
- Species filter narrows the observation count
- Table view shows observation data
- Clicking a table row opens the observation detail drawer (?obs= in URL)
- Filter state in the URL is preserved when the drawer is opened and closed
  (this is the key behaviour solved by the Vue Router + Pinia architecture -
  the old frontend would lose filter state on navigation)
"""

import datetime
import re

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observation(
    *,
    gbif_id: int,
    occurrence_id: str,
    species: Species,
    basis: BasisOfRecord,
) -> Observation:
    di = DataImport.objects.create(start=timezone.now())
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
    )


def _switch_to_table_view(page: Page) -> None:
    page.get_by_role("tab", name="Table").click()
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_index_page_renders(page: Page, live_server):
    """The index page loads: filter panel and observation counter are visible."""
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Filters", exact=True)).to_be_visible()
    expect(page.locator(".observation-counter")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_observation_counter_reflects_database(page: Page, live_server):
    """The counter shows the correct number of observations."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)
    _make_observation(gbif_id=2, occurrence_id="2", species=sp, basis=basis)

    page.goto(live_server.url + "/?status=all")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("2 matching observations")).to_be_visible()


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

    # Drawer is open - species name appears inside it
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

    # Navigate directly to the index with both a species filter and the drawer open
    page.goto(
        live_server.url + f"/?status=all&speciesIds={sp.pk}&obs={obs.stable_id}"
    )
    page.wait_for_load_state("networkidle")

    # Drawer should be open
    expect(page.locator('[data-pc-name="drawer"]')).to_be_visible()

    # Close the drawer via the X button
    page.get_by_role("button", name="Close").click()
    page.wait_for_load_state("networkidle")

    # ?obs= is gone; speciesIds filter is still present
    expect(page).not_to_have_url(re.compile(r"obs="))
    sp_pk = sp.pk
    expect(page).to_have_url(re.compile(rf"speciesIds={sp_pk}"))
