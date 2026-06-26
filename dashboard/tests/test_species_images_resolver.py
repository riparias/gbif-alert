# dashboard/tests/test_species_images_resolver.py
import requests_mock as requests_mock_module
from dashboard.species_images import (
    resolve_wikipedia_image,
    resolve_gbif_image,
    resolve_species_image,
)

WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/Vulpes%20vulpes"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
GBIF_SEARCH = "https://api.gbif.org/v1/occurrence/search"


def _wiki_summary_payload():
    return {
        "title": "Vulpes vulpes",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Red_fox"}},
        "originalimage": {
            "source": "https://upload.wikimedia.org/wikipedia/commons/3/30/Vulpes_vulpes.jpg"
        },
    }


def _commons_extmetadata_payload():
    return {
        "query": {
            "pages": {
                "-1": {
                    "imageinfo": [
                        {
                            "extmetadata": {
                                "Artist": {"value": "<a href='x'>Jane Doe</a>"},
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            }
                        }
                    ]
                }
            }
        }
    }


def test_resolve_wikipedia_image_happy_path():
    with requests_mock_module.Mocker() as m:
        m.get(WIKI_SUMMARY, json=_wiki_summary_payload())
        m.get(COMMONS_API, json=_commons_extmetadata_payload())
        result = resolve_wikipedia_image("Vulpes vulpes")
    assert result is not None
    assert result.image_url.endswith("Vulpes_vulpes.jpg")
    assert result.source_url == "https://en.wikipedia.org/wiki/Red_fox"
    assert result.attribution == "Jane Doe"  # HTML stripped
    assert result.license == "CC BY-SA 4.0"
    assert result.source_type == "wikipedia"


def test_resolve_wikipedia_image_no_image_returns_none():
    with requests_mock_module.Mocker() as m:
        m.get(WIKI_SUMMARY, json={"title": "Vulpes vulpes"})  # no originalimage
        assert resolve_wikipedia_image("Vulpes vulpes") is None


def test_resolve_wikipedia_image_404_returns_none():
    with requests_mock_module.Mocker() as m:
        m.get(WIKI_SUMMARY, status_code=404)
        assert resolve_wikipedia_image("Vulpes vulpes") is None


def test_resolve_gbif_image_happy_path():
    payload = {
        "results": [
            {
                "key": 123456,
                "media": [
                    {
                        "type": "StillImage",
                        "identifier": "https://example.org/fox.jpg",
                        "creator": "John Roe",
                        "license": "http://creativecommons.org/licenses/by/4.0/",
                    }
                ],
            }
        ]
    }
    with requests_mock_module.Mocker() as m:
        m.get(GBIF_SEARCH, json=payload)
        result = resolve_gbif_image(5219243)
    assert result is not None
    assert result.image_url == "https://example.org/fox.jpg"
    assert result.attribution == "John Roe"
    assert result.source_url == "https://www.gbif.org/occurrence/123456"
    assert result.source_type == "gbif"


def test_resolve_gbif_image_no_results_returns_none():
    with requests_mock_module.Mocker() as m:
        m.get(GBIF_SEARCH, json={"results": []})
        assert resolve_gbif_image(5219243) is None


def test_resolve_species_image_falls_back_to_gbif():
    with requests_mock_module.Mocker() as m:
        m.get(WIKI_SUMMARY, status_code=404)
        m.get(GBIF_SEARCH, json={
            "results": [{"key": 1, "media": [
                {"type": "StillImage", "identifier": "https://example.org/f.jpg",
                 "license": "CC0"}]}]})
        result = resolve_species_image("Vulpes vulpes", 5219243)
    assert result is not None
    assert result.source_type == "gbif"
