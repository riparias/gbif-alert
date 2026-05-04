"""End-to-end tests for the navbar species name display toggle.

Covers:
- Default mode is scientific (italicised Latin name).
- Toggling to vernacular updates rendering across the observations table.
- Preference persists across reload (cookie).
- Sort by species column re-fetches with the new orderBy when the toggle flips.
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
    Species,
)


@pytest.fixture
def two_observations(db):
    """One species with a vernacular, one without."""
    di = DataImport.objects.create(start=timezone.now())
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    dataset = Dataset.objects.create(name="DS", gbif_dataset_key="ds-key")

    species_with = Species.objects.create(
        name="Anas platyrhynchos",
        gbif_taxon_key=2498252,
        vernacular_name="Mallard",
    )
    species_without = Species.objects.create(
        name="Zeta vulgaris",
        gbif_taxon_key=9999999,
    )

    obs_with = Observation.objects.create(
        gbif_id="e2e-1",
        occurrence_id="occ:e2e-1",
        species=species_with,
        source_dataset=dataset,
        date=datetime.date(2024, 6, 1),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis,
        location=Point(5.0, 50.5, srid=4326),
    )
    obs_without = Observation.objects.create(
        gbif_id="e2e-2",
        occurrence_id="occ:e2e-2",
        species=species_without,
        source_dataset=dataset,
        date=datetime.date(2024, 6, 2),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis,
        location=Point(5.0, 50.5, srid=4326),
    )

    return {
        "obs_with": obs_with,
        "obs_without": obs_without,
        "species_with": species_with,
        "species_without": species_without,
    }


def _switch_to_table_view(page: Page) -> None:
    page.get_by_role("tab", name="Table").click()
    page.wait_for_load_state("networkidle")


def _click_toggle(page: Page) -> None:
    """Click the species name display toggle in the navbar."""
    page.locator(".gbif-species-name-toggle .p-toggleswitch").first.click()


@pytest.mark.django_db(transaction=True)
def test_default_mode_shows_scientific(live_server, page: Page, two_observations):
    """With no cookie, the table shows italicised scientific names."""
    page.goto(f"{live_server.url}/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    em = page.locator("em", has_text="Anas platyrhynchos").first
    expect(em).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_toggle_switches_to_vernacular(live_server, page: Page, two_observations):
    """Clicking the navbar toggle flips the rendering to vernacular."""
    page.goto(f"{live_server.url}/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    expect(page.locator("em", has_text="Anas platyrhynchos").first).to_be_visible()

    _click_toggle(page)
    page.wait_for_load_state("networkidle")

    # Species with vernacular shows the common name (no em)
    expect(page.locator("text=Mallard").first).to_be_visible()
    # Species without vernacular still shows scientific name in em + info icon
    expect(page.locator("em", has_text="Zeta vulgaris").first).to_be_visible()
    expect(page.locator(".pi-info-circle").first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_preference_persists_across_reload(live_server, page: Page, two_observations):
    """Setting vernacular mode persists after a full page reload."""
    page.goto(f"{live_server.url}/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    _click_toggle(page)
    page.wait_for_load_state("networkidle")
    expect(page.locator("text=Mallard").first).to_be_visible()

    page.reload()
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    expect(page.locator("text=Mallard").first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_sort_re_issues_when_preference_changes(
    live_server, page: Page, two_observations
):
    """While sorted on species, flipping the toggle re-fetches with the new orderBy."""
    page.goto(f"{live_server.url}/?status=all")
    page.wait_for_load_state("networkidle")
    _switch_to_table_view(page)

    # Click the Species column header to sort by it
    species_header = page.get_by_role("columnheader", name="Species")
    species_header.click()
    page.wait_for_load_state("networkidle")

    with page.expect_response(lambda r: "orderBy=vernacularName" in r.url) as resp_info:
        _click_toggle(page)
    response = resp_info.value
    assert response.status == 200
