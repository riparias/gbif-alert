import pytest
from django.contrib.auth import get_user_model

from dashboard.models import ApiToken

pytestmark = pytest.mark.django_db


def _user():
    return get_user_model().objects.create_user(
        username="tokuser", password="x", email="tok@example.com"
    )


def test_create_for_returns_raw_token_and_stores_hash():
    user = _user()
    token, raw = ApiToken.create_for(user, name="my script")
    assert raw  # a non-empty raw token is returned
    assert token.name == "my script"
    # Only the hash is stored, and it matches the raw value.
    assert token.token_hash == ApiToken.hash_token(raw)
    assert token.token_hash != raw
    # The prefix is a short, displayable slice of the raw token.
    assert raw.startswith(token.prefix)
    assert len(token.prefix) <= 12


def test_raw_token_is_not_recoverable_from_instance():
    user = _user()
    token, raw = ApiToken.create_for(user)
    # Reloading from the DB exposes only the hash/prefix, never the raw value.
    reloaded = ApiToken.objects.get(pk=token.pk)
    assert raw not in (reloaded.token_hash, reloaded.prefix)


def test_hash_token_is_deterministic():
    assert ApiToken.hash_token("abc") == ApiToken.hash_token("abc")
    assert ApiToken.hash_token("abc") != ApiToken.hash_token("abd")
