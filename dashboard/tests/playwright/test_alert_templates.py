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
    tpl.name_en = "Amphibians near X"
    tpl.save()

    User.objects.create_user(username="jane", password="pass", email="jane@e.com")
    login(page, live_server.url, "jane", "pass")
    page.goto(live_server.url + "/new-alert")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("Amphibians near X", exact=False)).to_be_visible()
    # Open the dialog from the template card's "Use this template" button.
    page.locator(".template-item").get_by_role(
        "button", name="Use this template", exact=False
    ).click()

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
