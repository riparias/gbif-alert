"""Tests for the opt-in EU funding acknowledgement in the footer.

The important case is the OFF one: GBIF Alert is a reusable tool, and an
instance that is not EU-funded must never display the EU emblem - that would
be a false claim of EU support, which the Horizon Europe Grant Agreement
(Art. 17.2) explicitly forbids. The setting therefore defaults to False and is
tested as such, not merely as "renders when enabled".
"""
import importlib

import pytest
from django.conf import settings as django_settings
from django.test import Client
from django.utils import translation

# The template tag module has a hyphen in its name, so it cannot be imported
# with a plain `from ... import ...`.
eu_emblem_path = importlib.import_module(
    "dashboard.templatetags.gbif-alert_extras"
).eu_funding_emblem_path

pytestmark = pytest.mark.django_db

# Any SPA-shell page renders the shared footer; the home page is the simplest.
_A_PAGE = "/"


def _set_flag(settings, enabled: bool) -> None:
    settings.GBIF_ALERT = {
        **settings.GBIF_ALERT,
        "SHOW_EU_FUNDING_ACKNOWLEDGEMENT": enabled,
    }


def test_no_eu_emblem_by_default():
    """A stock instance: nothing opted in, so nothing is shown.

    The key may be absent entirely - a `local_settings.py` that rebuilds
    `GBIF_ALERT` from scratch (as the shipped template does) will not have it -
    and that must render exactly like an explicit False. That the env-driven
    default is False is pinned in `test_settings.py`.
    """
    assert not django_settings.GBIF_ALERT.get("SHOW_EU_FUNDING_ACKNOWLEDGEMENT")

    content = Client().get(_A_PAGE).content.decode()

    assert "eu-funding" not in content
    assert "Funded by the European Union" not in content


def test_no_eu_emblem_when_disabled(settings):
    _set_flag(settings, False)

    content = Client().get(_A_PAGE).content.decode()

    assert "eu-funding" not in content
    assert "Funded by the European Union" not in content


def test_emblem_rendered_when_enabled(settings):
    _set_flag(settings, True)

    content = Client().get(_A_PAGE).content.decode()

    assert "/static/eu-funding/eu-funded-en-negative.png" in content
    assert 'alt="Funded by the European Union"' in content
    # The full disclaimer lives on the "about this site" page, one click away.
    assert 'href="/about-site"' in content


def test_emblem_matches_active_language(settings):
    _set_flag(settings, True)

    content = Client().get(_A_PAGE, headers={"accept-language": "fr"}).content.decode()

    assert "/static/eu-funding/eu-funded-fr-negative.png" in content
    assert "eu-funded-en" not in content


def test_emblem_falls_back_to_english_for_an_unshipped_language():
    """We only ship en/fr/nl; anything else must still get an emblem."""
    with translation.override("de"):
        assert eu_emblem_path() == "eu-funding/eu-funded-en.png"
        assert eu_emblem_path(negative=True) == "eu-funding/eu-funded-en-negative.png"


def test_emblem_path_handles_a_regional_language_code():
    """`get_language()` can return "en-us"; assets are named by base language."""
    with translation.override("en-us"):
        assert eu_emblem_path() == "eu-funding/eu-funded-en.png"


def test_emblem_path_per_shipped_language():
    for language_code in ("en", "fr", "nl"):
        with translation.override(language_code):
            assert eu_emblem_path() == f"eu-funding/eu-funded-{language_code}.png"
