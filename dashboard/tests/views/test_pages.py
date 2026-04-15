import json
import re
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.urls import reverse

from dashboard.models import Alert, Area, Dataset, Species

pytestmark = pytest.mark.django_db

_NAV_CONFIG_RE = re.compile(r'id="gbif-alert-nav-config"[^>]*>(.*?)</script>', re.DOTALL)


def _get_nav_config(response):
    content = response.content.decode()
    match = _NAV_CONFIG_RE.search(content)
    assert match is not None, "gbif-alert-nav-config script tag not found in response"
    return json.loads(match.group(1))


@pytest.fixture
def alert_pages_data():
    User = get_user_model()
    first_user = User.objects.create_user(
        username="frusciante", password="12345",
        first_name="John", last_name="Frusciante", email="frusciante@gmail.com",
    )
    second_user = User.objects.create_user(
        username="other_user", password="12345",
        first_name="Aaa", last_name="Bbb", email="otheruser@gmail.com",
    )
    first_species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    second_species = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
    public_area_andenne = Area.objects.create(
        name="Public polygon - Andenne",
        mpoly=MultiPolygon(
            Polygon(
                ((4.7866, 50.5200), (5.6271, 50.6839), (5.6930, 50.5724),
                 (4.8306, 50.4116), (4.7866, 50.5200)),
                srid=4326,
            ),
        ),
    )
    first_dataset = Dataset.objects.create(
        name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
    )
    alert = Alert.objects.create(
        name="Test alert", user=first_user, email_notifications_frequency="N",
    )
    alert.species.add(first_species)
    alert.datasets.add(first_dataset)
    alert.areas.add(public_area_andenne)
    first_user_area = Area.objects.create(
        name="First user polygon", owner=first_user,
        mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
    )
    second_user_area = Area.objects.create(
        name="Second user polygon", owner=second_user,
        mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
    )
    return {
        "first_user": first_user, "second_user": second_user,
        "alert": alert, "first_user_area": first_user_area, "second_user_area": second_user_area,
    }


@pytest.fixture
def nav_users():
    User = get_user_model()
    regular_user = User.objects.create_user(username="testuser", password="testpass123")
    superuser = User.objects.create_superuser(
        username="admin", password="adminpass123", email="admin@example.com"
    )
    return {"regular_user": regular_user, "superuser": superuser}


# --- IndexPageTests ---

def test_index_base(client):
    """The Vue SPA shell is served at /"""
    response = client.get("/")
    assert response.status_code == 200
    assert "dashboard/base.html" in [t.name for t in response.templates]


# --- AlertWebPagesTests ---

def test_user_can_access_own_alert_details(client, alert_pages_data):
    """Authenticated user gets the SPA shell for their alert detail page."""
    client.login(username="frusciante", password="12345")
    page_url = reverse("dashboard:pages:alert-details", kwargs={"alert_id": alert_pages_data["alert"].id})
    response = client.get(page_url)
    assert response.status_code == 200
    assert "dashboard/base.html" in [t.name for t in response.templates]


def test_anonymous_cant_access_alert_details(client, alert_pages_data):
    """An anonymous user is redirected to sign in when trying to see alert details."""
    page_url = reverse("dashboard:pages:alert-details", kwargs={"alert_id": alert_pages_data["alert"].id})
    response = client.get(page_url)
    assert response.status_code == 302


def test_otheruser_cant_access_alert_details(client, alert_pages_data):
    """An authenticated user cannot see another user's alert detail page."""
    client.login(username="other_user", password="12345")
    page_url = reverse("dashboard:pages:alert-details", kwargs={"alert_id": alert_pages_data["alert"].id})
    response = client.get(page_url)
    assert response.status_code == 404


def test_user_can_access_alert_create_page(client, alert_pages_data):
    """Authenticated user gets the SPA shell for the alert create page."""
    client.login(username="frusciante", password="12345")
    response = client.get(reverse("dashboard:pages:alert-create"))
    assert response.status_code == 200
    assert "dashboard/base.html" in [t.name for t in response.templates]


def test_anonymous_cant_access_alert_create(client):
    """Anonymous user is redirected when accessing alert create page."""
    response = client.get(reverse("dashboard:pages:alert-create"))
    assert response.status_code == 302


def test_user_can_access_alert_edit_page(client, alert_pages_data):
    """Authenticated user gets the SPA shell for their alert edit page."""
    client.login(username="frusciante", password="12345")
    page_url = reverse("dashboard:pages:alert-edit", kwargs={"alert_id": alert_pages_data["alert"].id})
    response = client.get(page_url)
    assert response.status_code == 200
    assert "dashboard/base.html" in [t.name for t in response.templates]


def test_otheruser_cant_access_alert_edit(client, alert_pages_data):
    """Another user cannot access alert edit page."""
    client.login(username="other_user", password="12345")
    page_url = reverse("dashboard:pages:alert-edit", kwargs={"alert_id": alert_pages_data["alert"].id})
    response = client.get(page_url)
    assert response.status_code == 404


def test_anonymous_cant_access_alert_edit(client, alert_pages_data):
    """Anonymous user is redirected when accessing alert edit page."""
    page_url = reverse("dashboard:pages:alert-edit", kwargs={"alert_id": alert_pages_data["alert"].id})
    response = client.get(page_url)
    assert response.status_code == 302


def test_user_can_access_my_alerts_page(client, alert_pages_data):
    """Authenticated user gets the SPA shell for the my-alerts page."""
    client.login(username="frusciante", password="12345")
    response = client.get(reverse("dashboard:pages:my-alerts"))
    assert response.status_code == 200
    assert "dashboard/base.html" in [t.name for t in response.templates]


def test_anonymous_cant_access_my_alerts(client):
    """Anonymous user is redirected when accessing my-alerts."""
    response = client.get(reverse("dashboard:pages:my-alerts"))
    assert response.status_code == 302


# --- NavConfigJsonTests ---

def test_json_present_on_every_page(client):
    """The nav config script tag is present on every page that uses base.html."""
    for url in ["/", reverse("dashboard:pages:news")]:
        response = client.get(url)
        assert 'id="gbif-alert-nav-config"' in response.content.decode()


def test_required_url_keys(client):
    """All URL keys the Vue navbar expects are present."""
    response = client.get("/")
    config = _get_nav_config(response)
    expected_keys = {
        "index", "news", "myAlerts", "aboutSite", "aboutData",
        "profile", "passwordChange", "myCustomAreas", "signout",
        "signin", "signup", "admin", "setLanguage",
    }
    assert set(config["urls"].keys()) == expected_keys


def test_anonymous_user_fields(client):
    """Anonymous users produce isAuthenticated=false, null username, all flags false."""
    response = client.get("/")
    user_data = _get_nav_config(response)["user"]
    assert not user_data["isAuthenticated"]
    assert user_data["username"] is None
    assert not user_data["isSuperuser"]
    assert not user_data["hasUnseenNews"]
    assert not user_data["hasAlertsWithUnseenObservations"]


def test_authenticated_user_fields(client, nav_users):
    """Authenticated users get isAuthenticated=true and their username."""
    client.login(username="testuser", password="testpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert user_data["isAuthenticated"]
    assert user_data["username"] == "testuser"
    assert not user_data["isSuperuser"]


@patch("dashboard.models.User.has_unseen_news", True)
def test_has_unseen_news_true(client, nav_users):
    """hasUnseenNews is true when the user has unseen news."""
    client.login(username="testuser", password="testpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert user_data["hasUnseenNews"]


@patch("dashboard.models.User.has_unseen_news", False)
def test_has_unseen_news_false(client, nav_users):
    """hasUnseenNews is false when the user has no unseen news."""
    client.login(username="testuser", password="testpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert not user_data["hasUnseenNews"]


@patch("dashboard.models.User.has_alerts_with_unseen_observations", True)
def test_has_unseen_observations_true(client, nav_users):
    """hasAlertsWithUnseenObservations is true when the user has unseen observations."""
    client.login(username="testuser", password="testpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert user_data["hasAlertsWithUnseenObservations"]


@patch("dashboard.models.User.has_alerts_with_unseen_observations", False)
def test_has_unseen_observations_false(client, nav_users):
    """hasAlertsWithUnseenObservations is false when the user has no unseen observations."""
    client.login(username="testuser", password="testpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert not user_data["hasAlertsWithUnseenObservations"]


def test_primary_palette_field(client):
    """primaryPalette is present in the nav config and is a non-empty string."""
    response = client.get("/")
    config = _get_nav_config(response)
    assert "primaryPalette" in config
    assert isinstance(config["primaryPalette"], str)
    assert config["primaryPalette"]


def test_superuser_flag(client, nav_users):
    """isSuperuser is true for superusers, false for regular users."""
    client.login(username="admin", password="adminpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert user_data["isSuperuser"]

    client.login(username="testuser", password="testpass123")
    user_data = _get_nav_config(client.get("/"))["user"]
    assert not user_data["isSuperuser"]
