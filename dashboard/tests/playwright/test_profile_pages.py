"""Playwright E2E tests for Phase 5 profile and content pages."""

import datetime

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from dashboard.models import DataImport
from dashboard.tests.playwright.helpers import login


@pytest.mark.django_db(transaction=True)
def test_about_site_page_renders(page: Page, live_server):
    """About site page loads and shows a heading."""
    page.goto(live_server.url + "/about-site")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="About this site", exact=False)).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_api_docs_page_renders(page: Page, live_server):
    """The /api-docs hub shows its heading and links to the v2 docs + WFS."""
    page.goto(live_server.url + "/api-docs")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="API", exact=False)).to_be_visible()
    expect(page.get_by_text("Open the API v2 docs", exact=False)).to_be_visible()
    # The v2 docs and WFS links are present.
    assert page.locator('a[href="/api/v2/docs"]').count() == 1
    assert page.locator('a[href="/api/wfs/observations"]').count() == 1


@pytest.mark.django_db(transaction=True)
def test_api_root_redirects_to_landing_page(page: Page, live_server):
    """Visiting bare /api/ lands the user on /api-docs."""
    page.goto(live_server.url + "/api/")
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(live_server.url + "/api-docs")


@pytest.mark.django_db(transaction=True)
def test_about_data_page_renders(page: Page, live_server):
    """About data page shows a data import entry."""
    DataImport.objects.create(
        start=datetime.datetime(2024, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2024, 3, 15, 11, 0, 0, tzinfo=datetime.timezone.utc),
        completed=True,
    )
    page.goto(live_server.url + "/about-data")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Data import #", exact=False)).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_news_page_renders(page: Page, live_server):
    """News page loads and shows a heading."""
    page.goto(live_server.url + "/whats-new")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="What's new", exact=False)).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_profile_page_loads(page: Page, live_server):
    """Profile page shows user data in the form."""
    User = get_user_model()
    User.objects.create_user(
        username="profiletest",
        password="pass1234",
        email="profile@t.com",
        first_name="Alice",
    )

    login(page, live_server.url, "profiletest", "pass1234")
    page.goto(live_server.url + "/profile")
    page.wait_for_load_state("networkidle")

    expect(page.locator("#p-firstname")).to_have_value("Alice")
    expect(page.locator("#p-email")).to_have_value("profile@t.com")


@pytest.mark.django_db(transaction=True)
def test_profile_save_succeeds(page: Page, live_server):
    """Changing first name and saving shows a success toast."""
    User = get_user_model()
    User.objects.create_user(
        username="profilesave",
        password="pass1234",
        email="psave@t.com",
        first_name="Bob",
    )

    login(page, live_server.url, "profilesave", "pass1234")
    page.goto(live_server.url + "/profile")
    page.wait_for_load_state("networkidle")

    page.locator("#p-firstname").fill("Charlie")
    page.get_by_role("button", name="Save profile").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator(".p-toast")).to_be_visible()
    expect(page.locator(".p-toast")).to_contain_text("profile", ignore_case=True)


@pytest.mark.django_db(transaction=True)
def test_api_token_create_and_revoke_via_ui(page: Page, live_server):
    """Dedicated /api-tokens page: create (raw value + sample curl shown once) then revoke."""
    User = get_user_model()
    User.objects.create_user(username="toktester", password="pass1234", email="tt@t.com")

    login(page, live_server.url, "toktester", "pass1234")
    page.goto(live_server.url + "/api-tokens")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="API tokens")).to_be_visible()
    expect(page.get_by_text("You don't have any API tokens yet.")).to_be_visible()

    # Create a token.
    page.get_by_placeholder("Token name", exact=False).fill("my script")
    page.get_by_role("button", name="Create token").click()

    # The raw token is shown once, and the token appears in the list.
    created = page.locator("[data-testid='created-token-value']")
    expect(created).to_be_visible()
    raw = created.input_value()
    assert raw  # non-empty raw token
    expect(page.get_by_text("my script")).to_be_visible()

    # A ready-to-run sample curl is shown, embedding the new token + the alerts endpoint.
    sample = page.locator("[data-testid='sample-curl']")
    expect(sample).to_be_visible()
    sample_text = sample.inner_text()
    assert raw in sample_text
    assert "/api/v2/alerts/" in sample_text
    assert "Authorization: Bearer" in sample_text

    # Revoke it.
    page.get_by_role("button", name="Revoke").click()
    page.get_by_role("button", name="Yes, I'm sure").click()
    expect(page.get_by_text("You don't have any API tokens yet.")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_delete_account_confirmed(page: Page, live_server):
    """Confirming account deletion removes the user and redirects to sign-in."""
    User = get_user_model()
    User.objects.create_user(username="todel", password="pass1234", email="todel@t.com")

    login(page, live_server.url, "todel", "pass1234")
    page.goto(live_server.url + "/profile")
    page.wait_for_load_state("networkidle")

    page.locator("[data-testid='delete-account-btn']").click()
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/accounts/signin/")
    assert not User.objects.filter(username="todel").exists()


@pytest.mark.django_db(transaction=True)
def test_delete_account_cancelled(page: Page, live_server):
    """Cancelling account deletion keeps the account intact."""
    User = get_user_model()
    User.objects.create_user(username="tokeep", password="pass1234", email="keep@t.com")

    login(page, live_server.url, "tokeep", "pass1234")
    page.goto(live_server.url + "/profile")
    page.wait_for_load_state("networkidle")

    page.locator("[data-testid='delete-account-btn']").click()
    page.get_by_role("button", name="Cancel").click()

    assert User.objects.filter(username="tokeep").exists()
