"""End-to-end tests for the search box of the filter modals (#433).

The species, dataset and area modals share one search helper
(assets/frontend/utils/fuzzyMatch.ts); the species modal is used here to
exercise it through the real UI.
"""

import pytest
from playwright.sync_api import Page, expect

from dashboard.models import Species


@pytest.fixture
def species(db):
    """Three species, one with an accented vernacular name."""
    Species.objects.create(
        name="Procyon lotor", gbif_taxon_key=1, vernacular_name="Raton laveur"
    )
    Species.objects.create(
        name="Procambarus fallax",
        gbif_taxon_key=2,
        vernacular_name="Ecrevisse marbr\u00e9e",
    )
    Species.objects.create(name="Zeta vulgaris", gbif_taxon_key=3)


def _search_species(page: Page, base_url: str, query: str):
    """Open the species filter modal, type `query`, return the dialog locator."""
    page.goto(base_url + "/?status=all")
    page.get_by_role("button", name="All species").click()
    dialog = page.get_by_role("dialog")
    dialog.locator(".species-search").fill(query)
    return dialog


@pytest.mark.django_db(transaction=True)
def test_misspelled_name_still_finds_species(page: Page, live_server, species):
    """A typo no longer empties the list: the request of #433.

    "Procyon lotro" (two letters swapped) is a substring of no name, so the
    typo-tolerant fallback must list Procyon lotor - and only it.
    """
    dialog = _search_species(page, live_server.url, "Procyon lotro")

    expect(dialog.get_by_text("Procyon lotor")).to_be_visible()
    expect(dialog.get_by_text("Procambarus fallax")).to_have_count(0)
    expect(dialog.get_by_text("Zeta vulgaris")).to_have_count(0)


@pytest.mark.django_db(transaction=True)
def test_exact_match_hides_near_misses(page: Page, live_server, species):
    """Typo tolerance is a fallback only, so it adds no noise to a good query.

    "Procy" is one edit away from the start of "Procambarus", but it is an
    exact substring of "Procyon lotor": only that species may be listed.
    """
    dialog = _search_species(page, live_server.url, "Procy")

    expect(dialog.get_by_text("Procyon lotor")).to_be_visible()
    expect(dialog.get_by_text("Procambarus fallax")).to_have_count(0)


@pytest.mark.django_db(transaction=True)
def test_search_ignores_accents(page: Page, live_server, species):
    """A name typed without its accents is still found.

    Leaving accents out is the most common "misspelling" of vernacular names
    on a multilingual instance, and used to return an empty list.
    """
    dialog = _search_species(page, live_server.url, "marbree")

    expect(dialog.get_by_text("Procambarus fallax")).to_be_visible()
    expect(dialog.get_by_text("Procyon lotor")).to_have_count(0)
