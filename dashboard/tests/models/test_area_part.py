import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

from dashboard.models import Area, AreaPart


def _mpoly():
    return MultiPolygon(
        Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
        srid=4326,
    )


@pytest.mark.django_db
def test_area_part_is_linked_to_its_area():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())
    part = AreaPart.objects.create(area=area, geom=area.mpoly[0])

    assert part.area == area
    assert list(area.parts.all()) == [part]


@pytest.mark.django_db
def test_deleting_an_area_deletes_its_parts():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())
    AreaPart.objects.create(area=area, geom=area.mpoly[0])

    area.delete()

    assert AreaPart.objects.count() == 0
