import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from dashboard.api_v2 import (
    api_v2,
    api_v2_anon_throttle,
    api_v2_auth_throttle,
    api_v2_signin_throttle,
)
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


def _signin(client, **extra):
    return client.post(
        "/api/v2/auth/signin/",
        {"username": "nobody", "password": "guess"},
        content_type="application/json",
        **extra,
    )


def test_signin_has_its_own_tight_throttle(client, monkeypatch):
    """Sign-in uses a dedicated bucket, separate from the global anon one."""
    assert api_v2_signin_throttle.rate == settings.API_V2_THROTTLE_SIGNIN
    cache.clear()
    monkeypatch.setattr(api_v2_signin_throttle, "num_requests", 2)
    assert _signin(client).status_code == 401
    assert _signin(client).status_code == 401
    assert _signin(client).status_code == 429
    # Other anonymous endpoints are unaffected by the sign-in bucket.
    assert client.get(reverse("api-v2:species_list")).status_code == 200


def test_signup_shares_the_signin_throttle(client, monkeypatch):
    cache.clear()
    monkeypatch.setattr(api_v2_signin_throttle, "num_requests", 1)
    assert _signin(client).status_code == 401
    resp = client.post("/api/v2/auth/signup/", {}, content_type="application/json")
    assert resp.status_code == 429


def test_spoofed_forwarded_for_does_not_reset_the_throttle(client, monkeypatch):
    """A client-chosen X-Forwarded-For prefix must not change the throttle key.

    The proxy appends the real client IP, so only the last entry counts.
    """
    assert settings.NINJA_NUM_PROXIES == 1
    cache.clear()
    monkeypatch.setattr(api_v2_signin_throttle, "num_requests", 2)
    codes = [
        _signin(client, HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 203.0.113.7").status_code
        for i in range(4)
    ]
    assert codes == [401, 401, 429, 429]
