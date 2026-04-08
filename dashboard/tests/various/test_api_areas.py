import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from dashboard.geo_utils import geojson_to_multipolygon
from dashboard.models import Area

User = get_user_model()


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


class GeoJSONToMultiPolygonTests(TestCase):
    def test_single_polygon_returns_multipolygon(self):
        result = geojson_to_multipolygon(SINGLE_POLYGON_FC)
        self.assertEqual(result.geom_type, "MultiPolygon")
        self.assertEqual(result.srid, 3857)
        self.assertEqual(len(result), 1)

    def test_two_polygon_features_merged(self):
        result = geojson_to_multipolygon(TWO_POLYGON_FC)
        self.assertEqual(result.geom_type, "MultiPolygon")
        self.assertEqual(len(result), 2)

    def test_multipolygon_feature_flattened(self):
        result = geojson_to_multipolygon(MULTIPOLYGON_FC)
        self.assertEqual(result.geom_type, "MultiPolygon")
        self.assertEqual(len(result), 2)

    def test_empty_feature_collection_raises(self):
        with self.assertRaises(ValueError):
            geojson_to_multipolygon({"type": "FeatureCollection", "features": []})

    def test_non_polygon_geometry_raises(self):
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
        with self.assertRaises(ValueError):
            geojson_to_multipolygon(fc)

    def test_reprojected_to_3857(self):
        result = geojson_to_multipolygon(SINGLE_POLYGON_FC, dest_srid=3857)
        # Coordinates should be large (Web Mercator, not lon/lat)
        centroid = result.centroid
        self.assertGreater(abs(centroid.x), 100_000)


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


class AreaFromDrawingAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="drawer", password="pass", email="drawer@t.com"
        )
        self.client.force_login(self.user)

    def test_create_from_drawing_returns_201(self):
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "My drawn area", "geojson": SIMPLE_FC}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["name"], "My drawn area")
        self.assertTrue(data["isUserSpecific"])
        self.assertIsInstance(data["id"], int)

    def test_create_from_drawing_requires_auth(self):
        self.client.logout()
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "Anon area", "geojson": SIMPLE_FC}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_create_from_drawing_invalid_geometry_returns_422(self):
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
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "Bad area", "geojson": bad_fc}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("detail", resp.json())

    def test_create_from_drawing_empty_fc_returns_422(self):
        empty_fc = {"type": "FeatureCollection", "features": []}
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "Empty", "geojson": empty_fc}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 422)
