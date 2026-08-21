import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command

from dashboard.models import Area, AreaPart


def _mpoly():
    return MultiPolygon(
        Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
        srid=4326,
    )


@pytest.mark.django_db
def test_rebuilds_parts_for_areas_that_bypassed_save():
    """bulk_create() does not call save(), so such areas start with no parts."""
    Area.objects.bulk_create([Area(name="Bulk", mpoly=_mpoly())])
    assert AreaPart.objects.count() == 0

    call_command("rebuild_area_parts")

    assert AreaPart.objects.count() >= 1


@pytest.mark.django_db
def test_rebuilding_a_single_area_leaves_the_others_alone():
    kept = Area.objects.create(name="Kept", mpoly=_mpoly())
    target = Area.objects.create(name="Target", mpoly=_mpoly())
    kept_part_ids = set(kept.parts.values_list("id", flat=True))

    call_command("rebuild_area_parts", "--area-id", str(target.pk))

    assert set(kept.parts.values_list("id", flat=True)) == kept_part_ids
