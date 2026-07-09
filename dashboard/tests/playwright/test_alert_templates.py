"""Playwright E2E for the alert templates feature."""

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from dashboard.models import Alert, AlertTemplate, Species
from dashboard.tests.playwright.helpers import login


@pytest.mark.django_db(transaction=True)
def test_user_creates_alert_from_template(page: Page, live_server):
    User = get_user_model()
    op = User.objects.create_superuser(username="op", password="pass", email="op@e.com")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    seed = Alert.objects.create(name="seed", user=op, email_notifications_frequency="N")
    seed.species.add(sp)
    tpl = AlertTemplate.create_from_alert(seed, created_by=op)
    tpl.name_en = "Amphibians near X"  # type: ignore[attr-defined]
    tpl.save()

    User.objects.create_user(username="jane", password="pass", email="jane@e.com")
    login(page, live_server.url, "jane", "pass")
    page.goto(live_server.url + "/new-alert")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("Amphibians near X", exact=False)).to_be_visible()

    # Scope to the card so we don't hit the confirm dialog's button of the same name.
    card = page.locator(".template-card").filter(has_text="Amphibians near X")

    # Reveal the collapsed details and check a species is listed there.
    card.get_by_role("button", name="Details", exact=False).click()
    expect(card.get_by_text("Procambarus fallax", exact=False)).to_be_visible()

    # Open the dialog from the template card's "Use this template" button.
    card.get_by_role("button", name="Use this template", exact=False).click()

    # Confirm dialog -> accept the suggested name. Scope to the PrimeVue dialog
    # itself so we don't hit the card button again (both share the same label).
    dialog = page.locator('[data-pc-name="dialog"]')
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Use this template", exact=False).click()
    page.wait_for_url("**/alert/**")

    jane = User.objects.get(username="jane")
    assert Alert.objects.filter(user=jane, created_from_template=tpl).exists()


@pytest.mark.django_db(transaction=True)
def test_publish_button_visible_only_to_superuser(page: Page, live_server):
    User = get_user_model()
    op = User.objects.create_superuser(username="op", password="pass", email="op@e.com")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    alert = Alert.objects.create(name="seed", user=op, email_notifications_frequency="N")
    alert.species.add(sp)

    login(page, live_server.url, "op", "pass")
    page.goto(live_server.url + f"/alert/{alert.pk}")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("button", name="Publish as template", exact=False)).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_publish_button_hidden_for_non_superuser(page: Page, live_server):
    User = get_user_model()
    jane = User.objects.create_user(username="jane", password="pass", email="jane@e.com")
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    alert = Alert.objects.create(name="jane's alert", user=jane, email_notifications_frequency="N")
    alert.species.add(sp)

    login(page, live_server.url, "jane", "pass")
    page.goto(live_server.url + f"/alert/{alert.pk}")
    page.wait_for_load_state("networkidle")

    # Sanity check: the page actually rendered for this user (sidebar actions are
    # only shown to authenticated users), so the absence of the publish button below
    # is a real assertion about the superuser gate, not a false negative from a
    # failed page load.
    expect(page.get_by_role("button", name="Edit this alert", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Publish as template", exact=False)).to_have_count(0)


@pytest.mark.django_db(transaction=True)
def test_expanded_template_card_species_list_does_not_overflow(page: Page, live_server):
    """Regression: a template with many species must wrap inside its card, not
    overflow horizontally. Before the fix the species list was one unbreakable
    line (each item nowrap, separators trapped inside), overflowing by ~1500px."""
    User = get_user_model()
    op = User.objects.create_superuser(username="op", password="pass", email="op@e.com")
    species = [
        Species.objects.create(name=f"Genus longspeciesname{i}", gbif_taxon_key=900000 + i)
        for i in range(20)
    ]
    seed = Alert.objects.create(name="many", user=op, email_notifications_frequency="N")
    seed.species.set(species)
    tpl = AlertTemplate.create_from_alert(seed, created_by=op)
    tpl.name_en = "Many species template"  # type: ignore[attr-defined]
    tpl.save()

    User.objects.create_user(username="bob", password="pass", email="bob@e.com")
    login(page, live_server.url, "bob", "pass")
    page.goto(live_server.url + "/new-alert")
    page.wait_for_load_state("networkidle")

    card = page.locator(".template-card").filter(has_text="Many species template")
    card.get_by_role("button", name="Details", exact=False).click()
    # Wait for the species list to be revealed before measuring.
    expect(card.locator(".detail-species")).to_be_visible()

    # The card must not overflow its grid track horizontally.
    overflow = card.evaluate("el => el.scrollWidth - el.clientWidth")
    assert overflow <= 2, f"template card overflows horizontally by {overflow}px"
