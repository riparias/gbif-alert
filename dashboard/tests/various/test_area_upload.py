from pathlib import Path

from django.contrib.gis.gdal import OGRGeometry, SpatialReference
from django.test import TestCase

from dashboard.views.pages import _file_to_wkt_multipolygon

THIS_SCRIPT_PATH = Path(__file__).parent
SAMPLE_DATA_PATH = THIS_SCRIPT_PATH / "sample_data"


class AreaUploadTests(TestCase):
    def assertCorrectPolygon(self, wkt: str | None) -> None:
        self.assertIsNotNone(wkt)
        geom = OGRGeometry(wkt, SpatialReference(3857))
        geom.transform(
            4326
        )  # Transform to WGS84 for easier comparison to points and debugging
        self.assertEqual(geom.geom_type, "MultiPolygon")
        # Only one polygon in the collection
        self.assertEqual(len(geom), 1)  # type: ignore
        # The polygon contains the Brussels airport, but not the Charleroi airport
        bru_airport = OGRGeometry(
            "POINT (4.483998064 50.90082973)", SpatialReference(4326)
        )
        crl_airport = OGRGeometry(
            "POINT (4.45166486 50.455998176)", SpatialReference(4326)
        )
        self.assertTrue(geom.contains(bru_airport))
        self.assertFalse(geom.contains(crl_airport))

    def test_uploaded_file_to_multipolygon_gpkg_polygon_3857(self):
        wkt = _file_to_wkt_multipolygon(
            SAMPLE_DATA_PATH / "polygon_3857.gpkg", dest_srid=3857
        )
        self.assertCorrectPolygon(wkt)

    def test_default_srid(self):
        wkt = _file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "polygon_3857.gpkg")
        self.assertCorrectPolygon(wkt)

    def test_uploaded_file_to_multipolygon_gpkg_multipolygon_3857(self):
        wkt = _file_to_wkt_multipolygon(
            SAMPLE_DATA_PATH / "multipolygon_3857.gpkg", dest_srid=3857
        )
        self.assertCorrectPolygon(wkt)

    def test_uploaded_file_to_multipolygon_gpkg_polygon_4326(self):
        wkt = _file_to_wkt_multipolygon(
            SAMPLE_DATA_PATH / "polygon_4326.gpkg", dest_srid=3857
        )
        self.assertCorrectPolygon(wkt)

    def test_uploaded_file_to_multipolygon_gpkg_polygon_lambert(self):
        wkt = _file_to_wkt_multipolygon(
            SAMPLE_DATA_PATH / "polygon_lambert.gpkg", dest_srid=3857
        )
        self.assertCorrectPolygon(wkt)

    def test_uploaded_file_to_multipolygon_gpkg_multipolygon_4326(self):
        wkt = _file_to_wkt_multipolygon(
            SAMPLE_DATA_PATH / "multipolygon_4326.gpkg", dest_srid=3857
        )
        self.assertCorrectPolygon(wkt)

    def test_uploaded_file_to_multipolygon_too_many_features(self):
        with self.assertRaisesRegexp(
            ValueError, "The file must contain a single feature, 2 features found"
        ):
            _file_to_wkt_multipolygon(
                SAMPLE_DATA_PATH / "polygon_4326_too_many_features.gpkg", dest_srid=3857
            )

    def test_uploaded_file_to_multipolygon_zero_features(self):
        with self.assertRaisesRegexp(
            ValueError, "The file must contain a single feature, 0 features found"
        ):
            _file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "empty.gpkg", dest_srid=3857)

    def test_uploaded_file_to_multipolygon_no_polygon_or_multipolygon(self):
        with self.assertRaisesRegexp(
            ValueError,
            "The file must contains a single layer of type Polygon or MultiPolygon, Point found",
        ):
            _file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "point.gpkg", dest_srid=3857)

    def test_uploaded_file_to_multipolygon_no_srs(self):
        # TODO: implement this, QGIS doesn't seem to allow to create a file without SRS
        pass
