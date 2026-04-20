"""Playwright E2E tests for Phase 5 auth pages (sign-in, sign-up, password-change)."""

import re

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from dashboard.tests.playwright.helpers import login


@pytest.mark.django_db(transaction=True)
def test_signin_succeeds(page: Page, live_server):
    """Valid credentials redirect to / and navbar shows username."""
    User = get_user_model()
    User.objects.create_user(username="auth1", password="pass1234", email="auth1@t.com")

    login(page, live_server.url, "auth1", "pass1234")

    # Path should be "/"; a trailing "?status=all" may appear because of
    # IndexPage's useFilterSync debounced URL sync.
    expect(page).to_have_url(
        re.compile(rf"^{re.escape(live_server.url)}/(\?.*)?$")
    )
    expect(page.get_by_text("auth1")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_signin_wrong_password(page: Page, live_server):
    """Wrong password shows an inline error and stays on the sign-in page."""
    User = get_user_model()
    User.objects.create_user(username="auth2", password="correct", email="auth2@t.com")

    page.goto(live_server.url + "/accounts/signin/")
    page.wait_for_load_state("networkidle")
    page.locator("#signin-username").fill("auth2")
    page.locator("#signin-password").fill("wrong")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator("[data-testid='signin-error']")).to_be_visible()
    expect(page).to_have_url(live_server.url + "/accounts/signin/")


@pytest.mark.django_db(transaction=True)
def test_signup_succeeds(page: Page, live_server):
    """Valid sign-up form creates an account and redirects to /."""
    User = get_user_model()

    page.goto(live_server.url + "/signup")
    page.wait_for_load_state("networkidle")
    page.locator("#su-username").fill("newauth3")
    page.locator("#su-email").fill("newauth3@t.com")
    page.locator("#su-password1").fill("Secure1234!")
    page.locator("#su-password2").fill("Secure1234!")
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/")
    assert User.objects.filter(username="newauth3").exists()


@pytest.mark.django_db(transaction=True)
def test_signup_duplicate_username_shows_error(page: Page, live_server):
    """Duplicate username shows a field-level error."""
    User = get_user_model()
    User.objects.create_user(username="existing", password="pass", email="ex@t.com")

    page.goto(live_server.url + "/signup")
    page.wait_for_load_state("networkidle")
    page.locator("#su-username").fill("existing")
    page.locator("#su-email").fill("other@t.com")
    page.locator("#su-password1").fill("Secure1234!")
    page.locator("#su-password2").fill("Secure1234!")
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/signup")
    expect(page.get_by_text("already exists", exact=False)).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_password_change_succeeds(page: Page, live_server):
    """Valid password change shows a success toast."""
    User = get_user_model()
    User.objects.create_user(username="auth5", password="OldPass123!", email="auth5@t.com")

    login(page, live_server.url, "auth5", "OldPass123!")
    page.goto(live_server.url + "/accounts/password-change/")
    page.wait_for_load_state("networkidle")

    page.locator("#cp-old").fill("OldPass123!")
    page.locator("#cp-new1").fill("NewPass456!")
    page.locator("#cp-new2").fill("NewPass456!")
    page.get_by_role("button", name="Change password").click()
    page.wait_for_load_state("networkidle")

    expect(page.locator(".p-toast")).to_be_visible()
    expect(page.locator(".p-toast")).to_contain_text("password", ignore_case=True)


@pytest.mark.django_db(transaction=True)
def test_password_change_wrong_old_password(page: Page, live_server):
    """Wrong old password shows a field error."""
    User = get_user_model()
    User.objects.create_user(username="auth6", password="Correct123!", email="auth6@t.com")

    login(page, live_server.url, "auth6", "Correct123!")
    page.goto(live_server.url + "/accounts/password-change/")
    page.wait_for_load_state("networkidle")

    page.locator("#cp-old").fill("wrong")
    page.locator("#cp-new1").fill("NewPass456!")
    page.locator("#cp-new2").fill("NewPass456!")
    page.get_by_role("button", name="Change password").click()
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("incorrect", exact=False)).to_be_visible()
