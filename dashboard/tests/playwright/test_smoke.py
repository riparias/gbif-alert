import re

import pytest
from django.test import Client
from playwright.sync_api import Page, expect


@pytest.mark.django_db(transaction=True)
def test_homepage_loads(page: Page, live_server):
    """Homepage returns a 200 response and does not render a server error page."""
    response = page.goto(live_server.url + "/")
    assert response is not None and response.ok
    expect(page).not_to_have_title(re.compile(r"Server Error"))


@pytest.mark.django_db(transaction=True)
def test_alert_detail_page_has_sidebar_layout(page: Page, live_server, django_user_model):
    """Alert detail page renders a two-column layout with a dark sidebar on the left."""
    from dashboard.models import Alert

    user = django_user_model.objects.create_user(username="sidebartest", password="pw")
    alert = Alert.objects.create(
        name="Sidebar Layout Alert",
        user=user,
        email_notifications_frequency="N",
    )

    # Force-login by injecting the Django session cookie into the Playwright context.
    django_client = Client()
    django_client.force_login(user)
    session_cookie = django_client.cookies["sessionid"]
    domain = live_server.url.split("://")[1].split(":")[0]
    page.context.add_cookies([
        {"name": "sessionid", "value": session_cookie.value, "domain": domain, "path": "/"},
    ])

    page.goto(f"{live_server.url}/alert/{alert.id}/")

    # Sidebar must be visible and contain the alert name (auto-waits for Vue to render)
    sidebar = page.locator(".alert-detail-sidebar")
    expect(sidebar).to_contain_text("Sidebar Layout Alert")
