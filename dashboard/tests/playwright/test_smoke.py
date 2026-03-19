import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db(transaction=True)
def test_homepage_loads(page: Page, live_server):
    """Homepage returns a 200 response and does not render a server error page."""
    response = page.goto(live_server.url + "/")
    assert response is not None and response.ok
    expect(page).not_to_have_title(re.compile(r"Server Error"))
