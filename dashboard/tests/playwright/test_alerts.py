"""Playwright E2E tests for Phase 3 alert CRUD pages.

Test data is created per-test (no shared state) using @pytest.mark.django_db(transaction=True).
"""

import re

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from dashboard.models import Alert, Species


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_species(name: str, key: int) -> Species:
    return Species.objects.create(name=name, gbif_taxon_key=key)


def _make_alert(user, name: str, *species) -> Alert:
    a = Alert.objects.create(name=name, user=user, email_notifications_frequency="N")
    a.species.add(*species)
    return a


def _login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(base_url + "/accounts/signin/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("#gbif-alert-signin-button")
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# /my-alerts tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_my_alerts_page_shows_alert_list(page: Page, live_server):
    """Authenticated user sees their alerts listed on /my-alerts."""
    User = get_user_model()
    user = User.objects.create_user(username="u1", password="pass", email="u1@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    _make_alert(user, "My test alert", sp)

    _login(page, live_server.url, "u1", "pass")
    page.goto(live_server.url + "/my-alerts")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("My test alert")).to_be_visible()
    expect(page.get_by_text("Procambarus fallax")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_my_alerts_empty_state(page: Page, live_server):
    """User with no alerts sees empty state message."""
    User = get_user_model()
    User.objects.create_user(username="u2", password="pass", email="u2@t.com")

    _login(page, live_server.url, "u2", "pass")
    page.goto(live_server.url + "/my-alerts")
    page.wait_for_load_state("networkidle")

    expect(
        page.get_by_text("don't currently have any configured alerts", exact=False)
    ).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_my_alerts_page_requires_login(page: Page, live_server):
    """Anonymous user is redirected away from /my-alerts."""
    page.goto(live_server.url + "/my-alerts")
    page.wait_for_load_state("networkidle")
    # Should be redirected to sign-in
    expect(page).not_to_have_url(live_server.url + "/my-alerts")


@pytest.mark.django_db(transaction=True)
def test_my_alerts_navigate_to_create(page: Page, live_server):
    """Clicking 'Create a new alert' navigates to /new-alert."""
    User = get_user_model()
    User.objects.create_user(username="u3", password="pass", email="u3@t.com")

    _login(page, live_server.url, "u3", "pass")
    page.goto(live_server.url + "/my-alerts")
    page.wait_for_load_state("networkidle")
    page.get_by_text("Create a new alert").first.click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/new-alert")


@pytest.mark.django_db(transaction=True)
def test_my_alerts_delete_alert(page: Page, live_server):
    """Deleting an alert from the list removes it and shows the updated list."""
    User = get_user_model()
    user = User.objects.create_user(username="u4", password="pass", email="u4@t.com")
    sp = _make_species("Orconectes virilis", 2227064)
    _make_alert(user, "Alert to delete", sp)

    _login(page, live_server.url, "u4", "pass")
    page.goto(live_server.url + "/my-alerts")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete this alert").click()
    # ConfirmDialog appears
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    # Wait for the alert card to disappear (the dialog title also contains the
    # name, so scope the check to the card container specifically).
    expect(page.locator(".alert-card").filter(has_text="Alert to delete")).not_to_be_visible()


# ---------------------------------------------------------------------------
# /new-alert tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_create_alert_form_renders(page: Page, live_server):
    """The create alert form renders with a pre-filled suggested name."""
    User = get_user_model()
    User.objects.create_user(username="u5", password="pass", email="u5@t.com")
    _make_species("Procambarus fallax", 8879526)

    _login(page, live_server.url, "u5", "pass")
    page.goto(live_server.url + "/new-alert")
    page.wait_for_load_state("networkidle")

    # Name input is pre-filled with the suggested name
    name_input = page.locator("#alert-name")
    expect(name_input).to_have_value("My alert #1")


@pytest.mark.django_db(transaction=True)
def test_create_alert_succeeds(page: Page, live_server):
    """Filling the form and saving creates the alert and navigates to its detail page."""
    User = get_user_model()
    user = User.objects.create_user(username="u6", password="pass", email="u6@t.com")
    _make_species("Procambarus fallax", 8879526)

    _login(page, live_server.url, "u6", "pass")
    page.goto(live_server.url + "/new-alert")
    page.wait_for_load_state("networkidle")

    # Select a species
    page.locator(".p-multiselect").filter(has_text="All species").click()
    page.get_by_text("Procambarus fallax").click()
    page.keyboard.press("Escape")

    # Save
    page.get_by_role("button", name="Create alert").click()

    # Wait for navigation to the alert detail page (URL changes to /alert/<id>).
    # Use wait_for_url with a pattern rather than networkidle because the detail
    # page fires background map requests that may produce 500s in the test DB
    # (hexa_5000 table is absent), and networkidle would then time out.
    page.wait_for_url(re.compile(r"/alert/\d+$"), timeout=10000)

    # Confirm the created alert exists in the DB and the URL matches.
    created_alert = Alert.objects.get(user=user)
    expect(page).to_have_url(live_server.url + f"/alert/{created_alert.pk}")


@pytest.mark.django_db(transaction=True)
def test_create_alert_shows_error_when_no_species(page: Page, live_server):
    """Saving without selecting any species shows a validation message."""
    User = get_user_model()
    User.objects.create_user(username="u7", password="pass", email="u7@t.com")

    _login(page, live_server.url, "u7", "pass")
    page.goto(live_server.url + "/new-alert")
    page.wait_for_load_state("networkidle")

    # The PrimeVue error Message for species must NOT be present before submission
    # (only the static field-hint paragraph is shown at this point).
    expect(page.locator("[data-pc-name='message']")).not_to_be_visible()

    page.get_by_role("button", name="Create alert").click()
    page.wait_for_load_state("networkidle")

    # After submitting with no species the server returns a validation error and
    # the PrimeVue <Message> component (data-pc-name="message") becomes visible.
    expect(page.locator("[data-pc-name='message']")).to_be_visible()


# ---------------------------------------------------------------------------
# /edit-alert/:alertId tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_edit_alert_form_pre_fills_existing_data(page: Page, live_server):
    """The edit form pre-fills with the existing alert's name."""
    User = get_user_model()
    user = User.objects.create_user(username="u8", password="pass", email="u8@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    alert = _make_alert(user, "Existing alert name", sp)

    _login(page, live_server.url, "u8", "pass")
    page.goto(live_server.url + f"/edit-alert/{alert.pk}")
    page.wait_for_load_state("networkidle")

    name_input = page.locator("#alert-name")
    expect(name_input).to_have_value("Existing alert name")


@pytest.mark.django_db(transaction=True)
def test_edit_alert_saves_changes(page: Page, live_server):
    """Editing an alert's name and saving shows the updated name on the detail page."""
    User = get_user_model()
    user = User.objects.create_user(username="u12", password="pass", email="u12@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    alert = _make_alert(user, "Original name", sp)

    _login(page, live_server.url, "u12", "pass")
    page.goto(live_server.url + f"/edit-alert/{alert.pk}")
    page.wait_for_load_state("networkidle")

    name_input = page.locator("#alert-name")
    name_input.click(click_count=3)
    name_input.fill("Updated alert name")

    page.get_by_role("button", name="Save").click()
    page.wait_for_url(re.compile(r"/alert/\d+$"), timeout=10000)

    expect(page.get_by_text("Updated alert name").first).to_be_visible()

    alert.refresh_from_db()
    assert alert.name == "Updated alert name"


@pytest.mark.django_db(transaction=True)
def test_my_alerts_delete_cancel_keeps_alert(page: Page, live_server):
    """Cancelling the delete confirmation dialog leaves the alert intact."""
    User = get_user_model()
    user = User.objects.create_user(username="u13", password="pass", email="u13@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    _make_alert(user, "Alert to keep", sp)

    _login(page, live_server.url, "u13", "pass")
    page.goto(live_server.url + "/my-alerts")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete this alert").click()
    # ConfirmDialog appears - dismiss it
    page.get_by_role("button", name="Cancel").click()

    # Alert card is still present
    expect(page.locator(".alert-card").filter(has_text="Alert to keep")).to_be_visible()


# ---------------------------------------------------------------------------
# /alert/:alertId tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_alert_detail_page_renders(page: Page, live_server):
    """Alert detail page renders the alert name and the observation table."""
    User = get_user_model()
    user = User.objects.create_user(username="u9", password="pass", email="u9@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    alert = _make_alert(user, "My detail alert", sp)

    _login(page, live_server.url, "u9", "pass")
    page.goto(live_server.url + f"/alert/{alert.pk}")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("My detail alert").first).to_be_visible()
    expect(page.get_by_text("Procambarus fallax").first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_alert_detail_edit_button_navigates(page: Page, live_server):
    """Clicking 'Edit this alert' on the detail page navigates to the edit form."""
    User = get_user_model()
    user = User.objects.create_user(username="u10", password="pass", email="u10@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    alert = _make_alert(user, "Editable alert", sp)

    _login(page, live_server.url, "u10", "pass")
    page.goto(live_server.url + f"/alert/{alert.pk}")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Edit this alert").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + f"/edit-alert/{alert.pk}")


@pytest.mark.django_db(transaction=True)
def test_alert_detail_delete_navigates_to_my_alerts(page: Page, live_server):
    """Deleting from the alert detail page navigates back to /my-alerts."""
    User = get_user_model()
    user = User.objects.create_user(username="u11", password="pass", email="u11@t.com")
    sp = _make_species("Procambarus fallax", 8879526)
    alert = _make_alert(user, "Alert to delete", sp)

    _login(page, live_server.url, "u11", "pass")
    page.goto(live_server.url + f"/alert/{alert.pk}")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete this alert").click()
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/my-alerts")
    assert not Alert.objects.filter(pk=alert.pk).exists()
