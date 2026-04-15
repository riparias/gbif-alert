from pathlib import Path

import pytest
from django.contrib.gis.gdal import OGRGeometry, SpatialReference

from dashboard.geo_utils import file_to_wkt_multipolygon

THIS_SCRIPT_PATH = Path(__file__).parent
SAMPLE_DATA_PATH = THIS_SCRIPT_PATH / "sample_data"


def assert_correct_polygon(wkt: str | None) -> None:
    assert wkt is not None
    geom = OGRGeometry(wkt, SpatialReference(3857))
    geom.transform(4326)
    assert geom.geom_type == "MultiPolygon"
    assert len(geom) == 1  # type: ignore[arg-type]
    bru_airport = OGRGeometry("POINT (4.483998064 50.90082973)", SpatialReference(4326))
    crl_airport = OGRGeometry("POINT (4.45166486 50.455998176)", SpatialReference(4326))
    assert geom.contains(bru_airport)
    assert not geom.contains(crl_airport)


def test_uploaded_file_to_multipolygon_gpkg_polygon_3857():
    wkt = file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "polygon_3857.gpkg", dest_srid=3857)
    assert_correct_polygon(wkt)


def test_default_srid():
    wkt = file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "polygon_3857.gpkg")
    assert_correct_polygon(wkt)


def test_uploaded_file_to_multipolygon_gpkg_multipolygon_3857():
    wkt = file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "multipolygon_3857.gpkg", dest_srid=3857)
    assert_correct_polygon(wkt)


def test_uploaded_file_to_multipolygon_gpkg_polygon_4326():
    wkt = file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "polygon_4326.gpkg", dest_srid=3857)
    assert_correct_polygon(wkt)


def test_uploaded_file_to_multipolygon_gpkg_polygon_lambert():
    wkt = file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "polygon_lambert.gpkg", dest_srid=3857)
    assert_correct_polygon(wkt)


def test_uploaded_file_to_multipolygon_gpkg_multipolygon_4326():
    wkt = file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "multipolygon_4326.gpkg", dest_srid=3857)
    assert_correct_polygon(wkt)


def test_uploaded_file_to_multipolygon_too_many_features():
    with pytest.raises(ValueError, match="The file must contain a single feature, 2 features found"):
        file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "polygon_4326_too_many_features.gpkg", dest_srid=3857)


def test_uploaded_file_to_multipolygon_zero_features():
    with pytest.raises(ValueError, match="The file must contain a single feature, 0 features found"):
        file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "empty.gpkg", dest_srid=3857)


def test_uploaded_file_to_multipolygon_no_polygon_or_multipolygon():
    with pytest.raises(
        ValueError,
        match="The file must contain a single layer of type Polygon or MultiPolygon, Point found",
    ):
        file_to_wkt_multipolygon(SAMPLE_DATA_PATH / "point.gpkg", dest_srid=3857)
