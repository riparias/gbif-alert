import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from dashboard.checks import check_areas_have_parts, check_download_geometry
from dashboard.models import Area, AreaPart


def _mpoly():
    return MultiPolygon(
        Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
        srid=4326,
    )


@pytest.mark.django_db
def test_no_warning_when_every_area_has_parts():
    Area.objects.create(name="Fine", mpoly=_mpoly())

    assert check_areas_have_parts(None) == []


@pytest.mark.django_db
def test_warns_about_an_area_without_parts():
    area = Area.objects.create(name="Orphan", mpoly=_mpoly())
    AreaPart.objects.filter(area=area).delete()

    warnings = check_areas_have_parts(None)

    assert len(warnings) == 1
    assert warnings[0].id == "dashboard.W001"
    assert "rebuild_area_parts" in warnings[0].hint


# Exterior ring anticlockwise, hole clockwise: the winding GBIF expects.
_ANTICLOCKWISE = "(0 0, 10 0, 10 10, 0 10, 0 0)"
_CLOCKWISE = "(0 0, 0 10, 10 10, 10 0, 0 0)"
_HOLE_CLOCKWISE = "(2 2, 2 4, 4 4, 4 2, 2 2)"
_HOLE_ANTICLOCKWISE = "(2 2, 4 2, 4 4, 2 4, 2 2)"


def test_no_error_without_download_geometry(settings):
    settings.GBIF_DOWNLOAD_GEOMETRY = ""

    assert check_download_geometry(None) == []


@pytest.mark.parametrize(
    "wkt",
    [
        f"POLYGON ({_ANTICLOCKWISE})",
        f"POLYGON ({_ANTICLOCKWISE}, {_HOLE_CLOCKWISE})",
        f"MULTIPOLYGON (({_ANTICLOCKWISE}, {_HOLE_CLOCKWISE}), "
        "((20 0, 30 0, 30 10, 20 10, 20 0)))",
    ],
)
def test_no_error_for_a_well_formed_download_geometry(settings, wkt):
    settings.GBIF_DOWNLOAD_GEOMETRY = wkt

    assert check_download_geometry(None) == []


@pytest.mark.parametrize(
    ("wkt", "expected_in_message"),
    [
        # A paste cut short, the likeliest accident with a long value.
        ("MULTIPOLYGON (((0 0, 10 0, 10 10", "not valid WKT"),
        ("not a geometry", "not valid WKT"),
        ("POINT (4 50)", "Polygon or MultiPolygon"),
        # Self-intersecting "bow tie".
        ("POLYGON ((0 0, 10 10, 10 0, 0 10, 0 0))", "invalid"),
        # GBIF reads a clockwise exterior ring as "everything outside".
        (f"POLYGON ({_CLOCKWISE})", "anticlockwise"),
        (
            f"MULTIPOLYGON (({_ANTICLOCKWISE}), ((20 0, 20 10, 30 10, 30 0, 20 0)))",
            "anticlockwise",
        ),
        (f"POLYGON ({_ANTICLOCKWISE}, {_HOLE_ANTICLOCKWISE})", "anticlockwise"),
    ],
)
def test_errors_on_a_bad_download_geometry(settings, wkt, expected_in_message):
    settings.GBIF_DOWNLOAD_GEOMETRY = wkt

    errors = check_download_geometry(None)

    assert len(errors) == 1
    assert errors[0].id == "dashboard.E001"
    assert "GBIF_DOWNLOAD_GEOMETRY" in errors[0].msg
    assert expected_in_message in errors[0].msg
