"""Playwright smoke tests for the /experiment UI experiment page."""

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


def _make_observation(
    *,
    gbif_id: int,
    occurrence_id: str,
    species: Species,
    basis: BasisOfRecord,
    dataset: Dataset | None = None,
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
    )


@pytest.mark.django_db(transaction=True)
def test_experiment_page_renders_sidebar(page: Page, live_server):
    """The experiment page loads with the sidebar filter panel visible."""
    page.goto(live_server.url + "/experiment/?status=all")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("FILTERS", exact=True)).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_experiment_page_has_three_tabs(page: Page, live_server):
    """The experiment page shows Map, Timeline, and Table tabs."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + "/experiment/?status=all")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("tab", name="Map")).to_be_visible()
    expect(page.get_by_role("tab", name="Timeline")).to_be_visible()
    expect(page.get_by_role("tab", name="Table")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_experiment_observation_count_in_sidebar(page: Page, live_server):
    """Sidebar stat block shows the live observation count."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)
    _make_observation(gbif_id=2, occurrence_id="2", species=sp, basis=basis)

    page.goto(live_server.url + "/experiment/?status=all")
    page.wait_for_load_state("networkidle")

    stat_block = page.locator(".stat-block")
    expect(stat_block).to_be_visible()
    expect(stat_block.get_by_text("2")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_experiment_drawer_opens_on_table_row_click(page: Page, live_server):
    """Clicking a table row on the experiment page opens the observation drawer."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    obs = _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + "/experiment/?status=all")
    page.wait_for_load_state("networkidle")

    page.get_by_role("tab", name="Table").click()
    page.wait_for_load_state("networkidle")

    page.locator("tbody tr").first.click()
    page.wait_for_url(re.compile(r"obs="))

    drawer = page.locator('[data-pc-name="drawer"]')
    expect(drawer).to_be_visible()
    expect(drawer.get_by_text(obs.species.name).first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_experiment_timeline_tab_shows_histogram(page: Page, live_server):
    """Clicking the Timeline tab shows the histogram chart."""
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    _make_observation(gbif_id=1, occurrence_id="1", species=sp, basis=basis)

    page.goto(live_server.url + "/experiment/?status=all")
    page.wait_for_load_state("networkidle")

    page.get_by_role("tab", name="Timeline").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator(".p-tabpanel:visible .histogram-svg")).to_be_visible()
