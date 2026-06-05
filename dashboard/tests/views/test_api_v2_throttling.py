import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from dashboard.api_v2 import api_v2, api_v2_anon_throttle, api_v2_auth_throttle
from dashboard.models import ApiToken

pytestmark = pytest.mark.django_db


def test_throttles_are_configured():
    """The public API carries the anon + auth throttles at the configured rates."""
    assert api_v2_anon_throttle in api_v2.throttle
    assert api_v2_auth_throttle in api_v2.throttle
    assert api_v2_anon_throttle.rate == settings.API_V2_THROTTLE_ANON
    assert api_v2_auth_throttle.rate == settings.API_V2_THROTTLE_AUTH


def test_anonymous_requests_are_throttled_per_ip(client, monkeypatch):
    """Anonymous reads are limited per IP (429 once the window is exceeded)."""
    cache.clear()
    monkeypatch.setattr(api_v2_anon_throttle, "num_requests", 2)
    url = reverse("api-v2:species_list")
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 429


def test_token_requests_are_throttled_per_user(client, django_user_model, monkeypatch):
    """Authenticated (token) requests are limited per user."""
    user = django_user_model.objects.create_user("thr", "thr@e.com", "pw")
    _, raw = ApiToken.create_for(user, "t")
    cache.clear()
    monkeypatch.setattr(api_v2_auth_throttle, "num_requests", 2)
    hdr = {"HTTP_AUTHORIZATION": f"Bearer {raw}"}
    assert client.get("/api/v2/alerts/", **hdr).status_code == 200
    assert client.get("/api/v2/alerts/", **hdr).status_code == 200
    assert client.get("/api/v2/alerts/", **hdr).status_code == 429
