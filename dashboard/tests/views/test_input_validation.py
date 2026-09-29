"""Malformed input on the map tile views and the legacy public API (#474).

Each of these used to raise inside the view, so Django answered 500 and
emailed ADMINS. They must answer 400 instead (logged as a warning, no email).
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

_TILES = "dashboard:internal-api:maps:mvt-tiles"
_HEX_TILES = "dashboard:internal-api:maps:mvt-tiles-hexagon-grid-aggregated"
_MIN_MAX = "dashboard:internal-api:maps:mvt-min-max-per-hexagon"
_DATA_PAGE = "dashboard:public-api:filtered-observations-data-page"
_COUNTER = "dashboard:public-api:filtered-observations-counter"
_POLYGON = "dashboard:public-api:species-per-polygon-json"


def _tile(url_name: str, zoom: int, x: int = 0, y: int = 0) -> str:
    return reverse(url_name, kwargs={"zoom": zoom, "x": x, "y": y})


@pytest.mark.parametrize(
    "url",
    [
        # No hexagon size past zoom 14 (ZOOM_TO_HEX_SIZE)
        _tile(_HEX_TILES, 15),
        # ST_TileEnvelope only takes zoom 0-31, and x/y within 2**zoom
        _tile(_TILES, 32),
        _tile(_TILES, 3, x=8),
        _tile(_TILES, 3, y=8),
        _tile(_HEX_TILES, 3, x=8),
        # Would compute 2**zoom on an unbounded integer before any check
        _tile(_TILES, 10**12),
    ],
)
def test_tile_out_of_range(client, url):
    assert client.get(url).status_code == 400


@pytest.mark.parametrize("zoom", ["15", "abc"])
def test_min_max_invalid_zoom(client, zoom):
    response = client.get(reverse(_MIN_MAX), data={"zoom": zoom})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "params",
    [
        {"speciesIds[]": "abc"},
        {"areaIds[]": "5-1"},  # reversed range
        {"startDate": "abc"},
        {"endDate": "2023-02-30"},
    ],
)
@pytest.mark.parametrize("url", [_tile(_TILES, 3), reverse(_COUNTER)])
def test_malformed_filter(client, url, params):
    assert client.get(url, data=params).status_code == 400


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "abc"},
        {"limit": "0"},
        {"limit": "-1"},
        {"limit": "1001"},
        {"page_number": "abc"},
        {"mode": "x"},
        {"order": "not_a_field"},
        # A real field, but not one we let callers sort on
        {"order": "species__vernacular_name_en"},
        {"order": "--date"},
    ],
)
def test_data_page_invalid_param(client, params):
    assert client.get(reverse(_DATA_PAGE), data=params).status_code == 400


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "1000"},
        {"order": "-source_dataset__name", "mode": "short"},
        {"order": "date"},
    ],
)
def test_data_page_valid_param(client, params):
    assert client.get(reverse(_DATA_PAGE), data=params).status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"p": ""},
        {"p": "abc"},
        {"p": "POLYGON(("},
        {"p": "SRID=3857;POINT(0 0)"},
        # Latitude out of range: the transform to the data SRID fails
        {"p": "POLYGON((0 0, 0 1000, 1000 1000, 1000 0, 0 0))"},
    ],
)
def test_species_per_polygon_invalid_polygon(client, params):
    assert client.get(reverse(_POLYGON), data=params).status_code == 400
