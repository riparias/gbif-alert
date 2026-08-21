import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from dashboard.checks import check_areas_have_parts
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
