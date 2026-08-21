"""The new parts-based area filter must select the same observations as the
ST_Within-against-the-whole-polygon filter it replaces."""

import datetime

import pytest
from django.contrib.gis.db.models.aggregates import Union as AggregateUnion
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import InternalError, transaction
from django.utils import timezone

from dashboard.models import (
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    Species,
)


@pytest.fixture
def observations_and_areas():
    di = DataImport.objects.create(start=timezone.now())
    dataset = Dataset.objects.create(name="D", gbif_dataset_key="k")
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)

    # A grid of points, some inside each area, some outside, some exactly on a
    # border (4.4 is the shared edge of `square` below).
    coords = [
        (4.35, 50.65),  # inside square
        (4.40, 50.65),  # exactly on square's right edge
        (4.45, 50.65),  # outside square, inside wide
        (9.00, 50.65),  # outside everything
    ]
    for i, (lon, lat) in enumerate(coords):
        Observation.objects.create(
            gbif_id=i,
            occurrence_id=str(i),
            species=species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=dataset,
            location=Point(lon, lat, srid=4326),
            basis_of_record=basis,
        )

    square = Area.objects.create(
        name="Square",
        mpoly=MultiPolygon(
            Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
            srid=4326,
        ),
    )
    wide = Area.objects.create(
        name="Wide",
        mpoly=MultiPolygon(
            Polygon(((4.0, 50.0), (5.0, 50.0), (5.0, 51.0), (4.0, 51.0), (4.0, 50.0))),
            srid=4326,
        ),
    )
    # A self-intersecting ("bowtie") polygon: 5 such areas exist in production
    # and they are the likeliest place for old and new to diverge.
    invalid = Area.objects.create(
        name="Bowtie",
        mpoly=MultiPolygon(
            Polygon(((4.3, 50.6), (4.5, 50.7), (4.3, 50.7), (4.5, 50.6), (4.3, 50.6))),
            srid=4326,
        ),
    )
    # Every value is an Area: the multi-area tests filter on
    # `observations_and_areas.values()`.
    return {"square": square, "wide": wide, "invalid": invalid}


def _old_filter_ids(area_ids):
    """The pre-subdivision implementation, kept here as the reference.

    Not exactly equivalent to the new one: this uses ST_Within, which excludes
    an observation lying exactly on an area's border, while the parts-based
    filter uses ST_Intersects and includes it. That is the deliberate semantics
    change from the design doc - asserted explicitly in
    test_an_observation_exactly_on_the_border_is_now_inside - and it is the only
    permitted difference between the two.
    """
    combined = Area.objects.filter(pk__in=area_ids).aggregate(
        area=AggregateUnion("mpoly")
    )["area"]
    return set(
        Observation.objects.filter(location__within=combined).values_list(
            "id", flat=True
        )
    )


def _new_filter_ids(area_ids):
    return set(
        Observation.objects.filtered_from_my_params(
            species_ids=[],
            datasets_ids=[],
            basis_of_record_ids=[],
            start_date=None,
            end_date=None,
            areas_ids=list(area_ids),
            status_for_user=None,
            initial_data_import_ids=[],
            user=None,
        ).values_list("id", flat=True)
    )


@pytest.mark.parametrize("key", ["wide", "invalid"])
@pytest.mark.django_db
def test_single_area_filter_matches_the_old_implementation(observations_and_areas, key):
    """`square` is excluded here: it is the one area with an observation exactly
    on its border, covered by the test below."""
    area_ids = [observations_and_areas[key].pk]
    assert _new_filter_ids(area_ids) == _old_filter_ids(area_ids)


@pytest.mark.django_db
def test_an_observation_exactly_on_the_border_is_now_inside(observations_and_areas):
    """The accepted semantics change: ST_Intersects includes the boundary.

    Measured impact on the LIFE RIPARIAS database was zero rows, but the change
    is real and reaches alert results, so it is asserted rather than tolerated.
    """
    area_ids = [observations_and_areas["square"].pk]
    # The observation sitting exactly on `square`'s right edge (4.40).
    on_border = Observation.objects.get(occurrence_id="1").pk

    old = _old_filter_ids(area_ids)
    new = _new_filter_ids(area_ids)

    assert on_border not in old, "ST_Within used to exclude the border"
    assert on_border in new, "ST_Intersects now includes it"
    assert new == old | {on_border}, "the border point is the ONLY difference"


@pytest.mark.django_db
def test_multi_area_filter_matches_the_old_implementation(observations_and_areas):
    """Only the valid areas: the old implementation cannot express the invalid
    case at all - see test_multi_area_filter_survives_an_invalid_geometry."""
    area_ids = [observations_and_areas[k].pk for k in ("square", "wide")]
    assert _new_filter_ids(area_ids) == _old_filter_ids(area_ids)


@pytest.mark.django_db
def test_multi_area_filter_survives_an_invalid_geometry(observations_and_areas):
    """Selecting several areas where one is self-intersecting used to crash.

    ST_Union raises a GEOS TopologyException on such geometries, so the old
    implementation returned a 500 for any filter combining them - reproduced on
    the LIFE RIPARIAS database with areas 1113/1115/1116. The parts-based filter
    never unions anything, so it simply works, and must return exactly what the
    per-area filters return together.
    """
    area_ids = [a.pk for a in observations_and_areas.values()]

    # Inside atomic(): the failed statement aborts its transaction, and the
    # savepoint rollback is what leaves the connection usable for the rest of
    # the test.
    with pytest.raises(InternalError), transaction.atomic():
        _old_filter_ids(area_ids)

    expected: set[int] = set()
    for area_id in area_ids:
        expected |= _old_filter_ids([area_id])

    assert _new_filter_ids(area_ids) == expected


@pytest.mark.django_db
def test_filtering_by_an_area_with_no_observations_returns_nothing(
    observations_and_areas,
):
    far_away = Area.objects.create(
        name="Far",
        mpoly=MultiPolygon(
            Polygon(((0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1), (0.0, 0.0))),
            srid=4326,
        ),
    )
    assert _new_filter_ids([far_away.pk]) == set()
