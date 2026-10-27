"""PageFragment translations: one Markdown text per language, with English as
the mandatory fallback."""

import pytest

from page_fragments.models import PageFragment

pytestmark = pytest.mark.django_db

URL = "/api/v2/spa/page-fragments/welcome_text/"


def test_page_fragment_is_served_in_every_site_language(client):
    """A fragment has a text for each language in settings.LANGUAGES, not only
    the original en/fr/nl: an instance running in Norwegian must be able to
    write its welcome, about and news pages in Norwegian."""
    PageFragment.objects.create(
        identifier="welcome_text", content_en="Welcome", content_nb="Velkommen"
    )

    resp = client.get(URL, HTTP_ACCEPT_LANGUAGE="nb")

    assert "Velkommen" in resp.json()["html"]


def test_page_fragment_falls_back_to_english(client):
    """A language with no text yet shows the English one rather than nothing,
    so a site can enable a language before every fragment is translated."""
    PageFragment.objects.create(identifier="welcome_text", content_en="Welcome")

    resp = client.get(URL, HTTP_ACCEPT_LANGUAGE="fr")

    assert "Welcome" in resp.json()["html"]


def test_page_fragment_admin_requires_english_content(admin_client):
    """English is the fallback for every other language, so the admin refuses
    a fragment without an English text: it would show nothing to anyone
    reading in a language that is not translated yet. The admin is the only
    place fragments are edited, and where modeltranslation enforces this."""
    resp = admin_client.post(
        "/admin/page_fragments/pagefragment/add/",
        {"identifier": "welcome_text", "content_fr": "Bienvenue"},
    )

    assert resp.status_code == 200  # form shown again, with errors
    assert "content_en" in resp.context["adminform"].form.errors
    assert not PageFragment.objects.filter(identifier="welcome_text").exists()
