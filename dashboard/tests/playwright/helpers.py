"""Shared helpers for Playwright browser tests."""

from playwright.sync_api import Page


def login(page: Page, base_url: str, username: str, password: str) -> None:
    """Log in via the Vue sign-in page and wait until fully on "/".

    SignInPage does ``window.location.href = "/"`` on success (a hard
    redirect). We wait for the URL to actually land on "/" rather than
    just for "a navigation to happen", because the latter can race with
    subsequent ``page.goto()`` calls on slow CI (observed:
    ``goto("/my-alerts")`` reported as "interrupted by another navigation
    to /" because the login redirect had not fully committed yet).

    Match by path only: IndexPage's ``useFilterSync`` debounces a
    ``router.replace`` that appends ``?status=all`` for authenticated
    users, so the post-login URL is either ``"/"`` or ``"/?status=all"``
    depending on timing.
    """
    page.goto(base_url + "/accounts/signin/")
    page.wait_for_load_state("networkidle")
    page.locator("#signin-username").fill(username)
    page.locator("#signin-password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(
        lambda url: url == base_url + "/" or url.startswith(base_url + "/?"),
        wait_until="networkidle",
    )
