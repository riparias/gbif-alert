"""Tests for the /healthz endpoint."""
import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_returns_200_and_json():
    client = Client()
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")

    body = json.loads(response.content)
    assert body == {"status": "ok"}


@pytest.mark.django_db
def test_healthz_does_not_require_authentication():
    """Healthz must work for anonymous requests so external probes can hit it."""
    client = Client()
    # No login.
    response = client.get("/healthz")
    assert response.status_code == 200
