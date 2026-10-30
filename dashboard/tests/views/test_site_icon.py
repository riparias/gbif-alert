"""Tests for the /site-icon.png endpoint and the pages that link to it."""
import pytest
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from maintenance_mode.core import set_maintenance_mode  # type: ignore

from dashboard.models import SiteIcon

# The view hands the stored bytes back as they are, it never decodes them.
ICON_BYTES = b"\x89PNG\r\n\x1a\nstored bytes"

MAINTENANCE_SETTINGS = {
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-site-icon-maintenance",
        }
    },
    "MAINTENANCE_MODE_STATE_BACKEND": "maintenance_mode.backends.CacheBackend",
}


@pytest.mark.django_db
def test_default_icon_redirects_to_static_file():
    """With no upload, an instance gets the neutral icon shipped in the engine.

    This is the whole point of #248: no instance should show another project's
    logo just because its operator has not picked an icon yet.
    """
    response = Client().get("/site-icon.png")

    assert response.status_code == 302
    assert response["Location"].endswith("site-icon-default.png")


@pytest.mark.django_db
def test_uploaded_icon_is_served_as_png():
    """Once an icon is stored, it is what visitors get, with the PNG type.

    A wrong content type would make browsers ignore the icon.
    """
    SiteIcon.objects.create(png=ICON_BYTES)

    response = Client().get("/site-icon.png")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content == ICON_BYTES


@pytest.mark.django_db
def test_icon_is_cacheable_for_a_day():
    """Browsers may keep the icon for a day.

    The image comes from Postgres: this header is what keeps it to about one
    query per browser per day instead of one per full page load.
    """
    SiteIcon.objects.create(png=ICON_BYTES)

    cache_control = Client().get("/site-icon.png")["Cache-Control"]

    assert "public" in cache_control
    assert "max-age=86400" in cache_control


@pytest.mark.django_db
def test_default_icon_redirect_is_cacheable_for_a_day():
    """The fallback gets the same lifetime as a stored icon.

    Most instances may never upload an icon, and an uncached redirect would make
    every full page load run the lookup for nothing.
    """
    assert "max-age=86400" in Client().get("/site-icon.png")["Cache-Control"]


@pytest.mark.django_db
@override_settings(**MAINTENANCE_SETTINGS)
def test_icon_is_served_during_maintenance():
    """The icon stays available while the site is in maintenance mode.

    The 503 page links to it, and imports keep an instance in maintenance mode
    for a long time. Without the exemption the icon request gets the 503 HTML
    and the browser tab loses its icon.
    """
    SiteIcon.objects.create(png=ICON_BYTES)
    cache.clear()
    client = Client()
    set_maintenance_mode(True)
    try:
        # Sanity: maintenance is genuinely on - a normal page is blocked (503).
        assert client.get("/").status_code == 503
        assert client.get("/site-icon.png").status_code == 200
    finally:
        set_maintenance_mode(False)


@pytest.mark.django_db
def test_regular_pages_link_to_the_icon():
    """Every page rendered by the SPA shell points browsers at the icon."""
    content = Client().get("/").content.decode()

    assert 'rel="icon"' in content
    assert 'href="/site-icon.png"' in content


@pytest.mark.django_db
@override_settings(**MAINTENANCE_SETTINGS)
def test_maintenance_page_links_to_the_icon():
    """The 503 page shows the instance's icon too.

    It is a separate template, so a change to the shell alone would not cover it.
    """
    cache.clear()
    client = Client()
    set_maintenance_mode(True)
    try:
        content = client.get("/").content.decode()
    finally:
        set_maintenance_mode(False)

    assert 'href="/site-icon.png"' in content


@pytest.mark.django_db
def test_page_render_does_not_query_for_the_icon():
    """Rendering a page never reads the icon table.

    This is the reason the link is a fixed URL: it keeps the image out of the
    queries of every page, even once an icon is stored.
    """
    SiteIcon.objects.create(png=ICON_BYTES)

    with CaptureQueriesContext(connection) as queries:
        Client().get("/")

    assert not [q for q in queries if "dashboard_siteicon" in q["sql"]]


def test_old_icon_files_are_gone():
    """The LIFE RIPARIAS icon no longer ships with the engine.

    An old path that still resolved would keep the logo reachable from a
    bookmark or a stale template.
    """
    assert finders.find("favicon-32x32.png") is None
    assert finders.find("apple-touch-icon.png") is None
    assert finders.find("site-icon-default.png") is not None
