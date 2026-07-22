import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile

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
                "coordinates": [
                    [[10.0, 50.0], [10.0, 51.0], [11.0, 51.0], [10.0, 50.0]]
                ],
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


def test_bare_polygon_geometry_accepted():
    geom = {
        "type": "Polygon",
        "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
    }
    result = geojson_to_multipolygon(geom)
    assert result.geom_type == "MultiPolygon"
    assert len(result) == 1


def test_bare_multipolygon_geometry_accepted():
    geom = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            [[[10.0, 50.0], [10.0, 51.0], [11.0, 51.0], [10.0, 50.0]]],
        ],
    }
    result = geojson_to_multipolygon(geom)
    assert result.geom_type == "MultiPolygon"
    assert len(result) == 2


def test_single_feature_accepted():
    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
        },
    }
    result = geojson_to_multipolygon(feature)
    assert result.geom_type == "MultiPolygon"
    assert len(result) == 1


def test_feature_without_geometry_raises_value_error():
    fc = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": None}],
    }
    with pytest.raises(ValueError, match="no geometry"):
        geojson_to_multipolygon(fc)


def test_malformed_coordinates_raise_value_error():
    """A GEOSException must surface as ValueError, not escape as a 500."""
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [[[4.0, 50.0]]]},
            }
        ],
    }
    with pytest.raises(ValueError):
        geojson_to_multipolygon(fc)


def test_unsupported_toplevel_type_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported GeoJSON type"):
        geojson_to_multipolygon({"type": "Point", "coordinates": [4.0, 50.0]})


def test_non_dict_input_raises_value_error():
    with pytest.raises(ValueError):
        geojson_to_multipolygon("not a dict")  # type: ignore[arg-type]


def test_non_list_features_raises_value_error():
    with pytest.raises(ValueError):
        geojson_to_multipolygon(
            {"type": "FeatureCollection", "features": {"a": 1}}  # type: ignore[dict-item]
        )


def test_non_dict_feature_raises_value_error():
    with pytest.raises(ValueError):
        geojson_to_multipolygon(
            {"type": "FeatureCollection", "features": ["nope"]}  # type: ignore[list-item]
        )


# ---------------------------------------------------------------------------
# AreaCreateAPITests
# ---------------------------------------------------------------------------


@pytest.fixture
def area_client(client):
    User = get_user_model()
    user = User.objects.create_user(
        username="drawer", password="pass", email="drawer@t.com"
    )
    client.force_login(user)
    return client


def test_create_returns_201(area_client):
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "My drawn area", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My drawn area"
    assert data["isUserSpecific"]
    assert isinstance(data["id"], int)


def test_create_requires_auth(client):
    resp = client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Anon area", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_create_invalid_geometry_returns_422(area_client):
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
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Bad area", "geojson": bad_fc}),
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_create_empty_fc_returns_422(area_client):
    empty_fc = {"type": "FeatureCollection", "features": []}
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Empty", "geojson": empty_fc}),
        content_type="application/json",
    )
    assert resp.status_code == 422


@pytest.fixture
def operator_client(client):
    User = get_user_model()
    operator = User.objects.create_superuser("boss", "boss@t.com", "pass")
    client.force_login(operator)
    return client


def test_operator_can_create_shared_area(operator_client):
    resp = operator_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Shared area", "geojson": SIMPLE_FC, "shared": True}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["isUserSpecific"] is False
    assert Area.objects.get(name="Shared area").owner is None


def test_shared_area_is_visible_to_another_user(operator_client, django_user_model):
    resp = operator_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Shared area", "geojson": SIMPLE_FC, "shared": True}),
        content_type="application/json",
    )
    assert resp.status_code == 201

    from django.test import Client

    other = django_user_model.objects.create_user(
        username="bystander", password="pass", email="by@t.com"
    )
    other_client = Client()
    other_client.force_login(other)
    names = [a["name"] for a in other_client.get("/api/v2/areas/").json()]
    assert "Shared area" in names


def test_operator_without_shared_flag_creates_user_specific_area(operator_client):
    resp = operator_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "My own area", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["isUserSpecific"] is True
    assert Area.objects.get(name="My own area").owner is not None


def test_regular_user_asking_for_shared_gets_403(area_client):
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Sneaky", "geojson": SIMPLE_FC, "shared": True}),
        content_type="application/json",
    )
    assert resp.status_code == 403
    assert not Area.objects.filter(name="Sneaky").exists()


def test_shared_permission_checked_before_geometry(area_client):
    """A non-operator gets 403, not 422, even with an unusable geometry."""
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps(
            {
                "name": "Sneaky",
                "geojson": {"type": "FeatureCollection", "features": []},
                "shared": True,
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 403


def test_shared_permission_checked_before_geometry_on_file_upload(area_client):
    """Non-operator gets 403 on multipart shared-area POST, before the file is parsed."""
    dummy_file = SimpleUploadedFile(
        name="invalid.gpkg",
        content=b"not a valid geopackage",
        content_type="application/octet-stream",
    )
    resp = area_client.post(
        "/api/v2/areas/from-file/",
        {
            "name": "Sneaky",
            "data_file": dummy_file,
            "shared": "true",
        },
    )
    assert resp.status_code == 403
    assert not Area.objects.filter(name="Sneaky").exists()


def test_create_with_tags(area_client):
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps(
            {"name": "Tagged", "geojson": SIMPLE_FC, "tags": ["provinces", "belgium"]}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert sorted(resp.json()["tags"]) == ["belgium", "provinces"]
    area = Area.objects.get(name="Tagged")
    assert sorted(t.name for t in area.tags.all()) == ["belgium", "provinces"]


def test_create_without_tags_has_no_tags(area_client):
    resp = area_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Untagged", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["tags"] == []


def test_create_from_file_accepts_tags_and_shared(operator_client, tmp_path):
    """The multipart creator has the same capabilities as the JSON one."""
    geojson_path = tmp_path / "area.geojson"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": SIMPLE_FC["features"],
            }
        )
    )
    with geojson_path.open("rb") as fh:
        resp = operator_client.post(
            "/api/v2/areas/from-file/",
            data={
                "name": "From file",
                "data_file": fh,
                "shared": "true",
                "tags": ["provinces", "belgium"],
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["isUserSpecific"] is False
    assert sorted(body["tags"]) == ["belgium", "provinces"]


def test_create_from_file_duplicate_name_returns_409(operator_client, tmp_path):
    """The multipart creator enforces the same per-scope name uniqueness as the JSON one."""
    geojson_path = tmp_path / "area.geojson"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": SIMPLE_FC["features"],
            }
        )
    )
    with geojson_path.open("rb") as fh:
        first = operator_client.post(
            "/api/v2/areas/from-file/",
            data={"name": "From file twice", "data_file": fh, "shared": "true"},
        )
    assert first.status_code == 201

    with geojson_path.open("rb") as fh:
        second = operator_client.post(
            "/api/v2/areas/from-file/",
            data={"name": "From file twice", "data_file": fh, "shared": "true"},
        )
    assert second.status_code == 409
    assert "detail" in second.json()
    assert Area.objects.filter(name="From file twice").count() == 1


def test_duplicate_name_same_owner_returns_409(area_client):
    payload = json.dumps({"name": "Twice", "geojson": SIMPLE_FC})
    first = area_client.post(
        "/api/v2/areas/", data=payload, content_type="application/json"
    )
    assert first.status_code == 201
    second = area_client.post(
        "/api/v2/areas/", data=payload, content_type="application/json"
    )
    assert second.status_code == 409
    assert "detail" in second.json()
    assert Area.objects.filter(name="Twice").count() == 1


def test_duplicate_name_across_scopes_is_allowed(operator_client, django_user_model):
    shared = operator_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Antwerpen", "geojson": SIMPLE_FC, "shared": True}),
        content_type="application/json",
    )
    assert shared.status_code == 201

    from django.test import Client

    user = django_user_model.objects.create_user(
        username="regular", password="pass", email="reg@t.com"
    )
    user_client = Client()
    user_client.force_login(user)
    private = user_client.post(
        "/api/v2/areas/",
        data=json.dumps({"name": "Antwerpen", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert private.status_code == 201
    assert Area.objects.filter(name="Antwerpen").count() == 2


def test_two_shared_areas_cannot_share_a_name(operator_client):
    payload = json.dumps({"name": "Shared twice", "geojson": SIMPLE_FC, "shared": True})
    assert (
        operator_client.post(
            "/api/v2/areas/", data=payload, content_type="application/json"
        ).status_code
        == 201
    )
    assert (
        operator_client.post(
            "/api/v2/areas/", data=payload, content_type="application/json"
        ).status_code
        == 409
    )


# ---------------------------------------------------------------------------
# AreaPatchAPITests
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_data(client):
    User = get_user_model()
    user = User.objects.create_user(
        username="patcher", password="pass", email="patcher@t.com"
    )
    other = User.objects.create_user(
        username="other", password="pass", email="other@t.com"
    )
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
    other_area = Area.objects.create(
        name="Other area", owner=patch_data["other"], mpoly=SIMPLE_MPOLY
    )
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


def test_patch_sets_tags(patch_data):
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"tags": ["rivers"]}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["rivers"]


def test_patch_tags_replaces_the_whole_set(patch_data):
    patch_data["area"].tags.set(["old", "stale"])
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"tags": ["fresh"]}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert [t.name for t in patch_data["area"].tags.all()] == ["fresh"]


def test_patch_without_tags_leaves_them_unchanged(patch_data):
    patch_data["area"].tags.set(["keepme"])
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "Renamed again"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert [t.name for t in patch_data["area"].tags.all()] == ["keepme"]


def test_patch_empty_tag_list_clears_tags(patch_data):
    patch_data["area"].tags.set(["gone"])
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"tags": []}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert list(patch_data["area"].tags.all()) == []


def test_patch_rename_onto_taken_name_returns_409(patch_data):
    Area.objects.create(name="Taken", owner=patch_data["user"], mpoly=SIMPLE_MPOLY)
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "Taken"}),
        content_type="application/json",
    )
    assert resp.status_code == 409
    patch_data["area"].refresh_from_db()
    assert patch_data["area"].name == "Original"


def test_patch_with_own_unchanged_name_returns_200(patch_data):
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{patch_data['area'].pk}/",
        data=json.dumps({"name": "Original", "geojson": SIMPLE_FC}),
        content_type="application/json",
    )
    assert resp.status_code == 200


def test_operator_can_patch_a_shared_area(operator_client):
    public_area = Area.objects.create(name="Public", owner=None, mpoly=SIMPLE_MPOLY)
    resp = operator_client.patch(
        f"/api/v2/areas/{public_area.pk}/",
        data=json.dumps({"name": "Public renamed"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    public_area.refresh_from_db()
    assert public_area.name == "Public renamed"


def test_operator_can_delete_a_shared_area(operator_client):
    public_area = Area.objects.create(name="Public", owner=None, mpoly=SIMPLE_MPOLY)
    resp = operator_client.delete(f"/api/v2/areas/{public_area.pk}/")
    assert resp.status_code == 204
    assert not Area.objects.filter(pk=public_area.pk).exists()


def test_regular_user_cannot_patch_a_shared_area(patch_data):
    public_area = Area.objects.create(name="Public", owner=None, mpoly=SIMPLE_MPOLY)
    resp = patch_data["client"].patch(
        f"/api/v2/areas/{public_area.pk}/",
        data=json.dumps({"name": "Hijacked"}),
        content_type="application/json",
    )
    assert resp.status_code == 404
    public_area.refresh_from_db()
    assert public_area.name == "Public"


def test_regular_user_cannot_delete_a_shared_area(patch_data):
    public_area = Area.objects.create(name="Public", owner=None, mpoly=SIMPLE_MPOLY)
    resp = patch_data["client"].delete(f"/api/v2/areas/{public_area.pk}/")
    assert resp.status_code == 404
    assert Area.objects.filter(pk=public_area.pk).exists()


def test_operator_cannot_patch_another_users_private_area(
    operator_client, django_user_model
):
    """Operators get access to site content, not to other people's private areas."""
    owner = django_user_model.objects.create_user(
        username="privateowner", password="pass", email="po@t.com"
    )
    private_area = Area.objects.create(name="Private", owner=owner, mpoly=SIMPLE_MPOLY)
    resp = operator_client.patch(
        f"/api/v2/areas/{private_area.pk}/",
        data=json.dumps({"name": "Snooped"}),
        content_type="application/json",
    )
    assert resp.status_code == 404
    private_area.refresh_from_db()
    assert private_area.name == "Private"
