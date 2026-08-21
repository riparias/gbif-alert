import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection

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
    # Not an equality check on the whole set: saving the area already built its
    # own parts, so this one is an extra alongside them.
    assert part in area.parts.all()


@pytest.mark.django_db
def test_deleting_an_area_deletes_its_parts():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())
    AreaPart.objects.create(area=area, geom=area.mpoly[0])

    area.delete()

    assert AreaPart.objects.count() == 0


def _bigger_mpoly():
    return MultiPolygon(
        Polygon(((4.0, 50.0), (5.0, 50.0), (5.0, 51.0), (4.0, 51.0), (4.0, 50.0))),
        srid=4326,
    )


@pytest.mark.django_db
def test_saving_a_new_area_creates_its_parts():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())

    assert area.parts.count() >= 1


@pytest.mark.django_db
def test_editing_the_geometry_replaces_the_parts():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())
    before = set(area.parts.values_list("id", flat=True))

    area.mpoly = _bigger_mpoly()
    area.save()

    after = set(area.parts.values_list("id", flat=True))
    assert before.isdisjoint(after), "old parts should have been replaced"
    assert area.parts.count() >= 1


@pytest.mark.django_db
def test_rebuild_parts_is_idempotent():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())
    count_before = area.parts.count()

    area.rebuild_parts()

    assert area.parts.count() == count_before


@pytest.mark.django_db
def test_parts_cover_the_original_geometry():
    """The pieces reassemble into the area, up to floating-point dust.

    ST_Equals is deliberately not used: it reports False for a difference of
    ~1e-6 m2 along the subdivision cut lines.
    """
    area = Area.objects.create(name="Region X", mpoly=_bigger_mpoly())
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT ST_Area(ST_SymDifference(ST_Union(p.geom), a.mpoly))
            FROM dashboard_areapart p JOIN dashboard_area a ON a.id = p.area_id
            WHERE a.id = %s GROUP BY a.mpoly
            """,
            [area.pk],
        )
        symmetric_difference = cur.fetchone()[0]

    assert symmetric_difference < 0.001  # square metres
