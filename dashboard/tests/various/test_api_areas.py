import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon

from dashboard.geo_utils import geojson_to_multipolygon
from dashboard.models import Area

pytestmark = pytest.mark.django_db

SINGLE_POLYGON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            },
            "properties": {},
        }
    ],
}

TWO_POLYGON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            },
            "properties": {},
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[10.0, 50.0], [10.0, 51.0], [11.0, 51.0], [10.0, 50.0]]],
            },
            "properties": {},
        },
    ],
}

MULTIPOLYGON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
                    [[[10.0, 50.0], [10.0, 51.0], [11.0, 51.0], [10.0, 50.0]]],
                ],
            },
            "properties": {},
        }
    ],
}

SIMPLE_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            },
            "properties": {},
        }
    ],
}

SIMPLE_MPOLY = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)), srid=4326))


# ---------------------------------------------------------------------------
# GeoJSONToMultiPolygonTests
# ---------------------------------------------------------------------------

def test_single_polygon_returns_multipolygon():
    result = geojson_to_multipolygon(SINGLE_POLYGON_FC)
    assert result.geom_type == "MultiPolygon"
    assert result.srid == 3857
    assert len(result) == 1


def test_two_polygon_features_merged():
    result = geojson_to_multipolygon(TWO_POLYGON_FC)
    assert result.geom_type == "MultiPolygon"
    assert len(result) == 2


def test_multipolygon_feature_flattened():
    result = geojson_to_multipolygon(MULTIPOLYGON_FC)
    assert result.geom_type == "MultiPolygon"
    assert len(result) == 2


def test_empty_feature_collection_raises():
    with pytest.raises(ValueError):
        geojson_to_multipolygon({"type": "FeatureCollection", "features": []})


def test_non_polygon_geometry_raises():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [4.0, 50.0]},
                "properties": {},
            }
        ],
    }
    with pytest.raises(ValueError):
        geojson_to_multipolygon(fc)


def test_reprojected_to_3857():
    result = geojson_to_multipolygon(SINGLE_POLYGON_FC, dest_srid=3857)
    centroid = result.centroid
    assert abs(centroid.x) > 100_000


# ---------------------------------------------------------------------------
# AreaFromDrawingAPITests
# ---------------------------------------------------------------------------

@pytest.fixture
def drawing_client(client):
    User = get_user_model()
    user = User.objects.create_user(username="drawer", password="pass", email="drawer@t.com")
    client.force_login(user)
    return client


def test_create_from_drawing_returns_201(drawing_client):
    resp = drawing_client.post(
        "/api/v2/areas/from-drawing/",
        data=json.dumps({"name": "My drawn area", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My drawn area"
    assert data["isUserSpecific"]
    assert isinstance(data["id"], int)


def test_create_from_drawing_requires_auth(client):
    resp = client.post(
        "/api/v2/areas/from-drawing/",
        data=json.dumps({"name": "Anon area", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_create_from_drawing_invalid_geometry_returns_422(drawing_client):
    bad_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [4.0, 50.0]},
                "properties": {},
            }
        ],
    }
    resp = drawing_client.post(
        "/api/v2/areas/from-drawing/",
        data=json.dumps({"name": "Bad area", "geojson": bad_fc}),
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_create_from_drawing_empty_fc_returns_422(drawing_client):
    empty_fc = {"type": "FeatureCollection", "features": []}
    resp = drawing_client.post(
        "/api/v2/areas/from-drawing/",
        data=json.dumps({"name": "Empty", "geojson": empty_fc}),
        content_type="application/json",
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AreaPatchAPITests
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_data(client):
    User = get_user_model()
    user = User.objects.create_user(username="patcher", password="pass", email="patcher@t.com")
    other = User.objects.create_user(username="other", password="pass", email="other@t.com")
    area = Area.objects.create(name="Original", owner=user, mpoly=SIMPLE_MPOLY)
    client.force_login(user)
    return {"client": client, "user": user, "other": other, "area": area}


def test_patch_name_returns_200(patch_data):
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "Renamed"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    patch_data["area"].refresh_from_db()
    assert patch_data["area"].name == "Renamed"


def test_patch_geometry_returns_200(patch_data):
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "Original", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    patch_data["area"].refresh_from_db()
    assert patch_data["area"].mpoly.geom_type == "MultiPolygon"


def test_patch_null_geojson_leaves_geometry_unchanged(patch_data):
    original_wkt = patch_data["area"].mpoly.wkt
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "New name", "geojson": None}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    patch_data["area"].refresh_from_db()
    assert patch_data["area"].mpoly.wkt == original_wkt


def test_patch_another_users_area_returns_404(patch_data):
    other_area = Area.objects.create(name="Other area", owner=patch_data["other"], mpoly=SIMPLE_MPOLY)
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{other_area.pk}/",
        data=json.dumps({"name": "Hijacked"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_patch_nonexistent_area_returns_404(patch_data):
    resp = patch_data["client"].patch(
        "/api/v2/areas/99999/",
        data=json.dumps({"name": "Ghost"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_patch_requires_auth(patch_data, client):
    client.logout()
    resp = client.patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "Anon"}),
        content_type="application/json",
    )
    assert resp.status_code == 401
