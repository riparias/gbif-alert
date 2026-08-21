"""The new parts-based area filter must select the same observations as the
ST_Within-against-the-whole-polygon filter it replaces."""

import pytest
from django.contrib.gis.db.models.aggregates import Union as AggregateUnion
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import InternalError, transaction

from dashboard.models import Area, Observation, Species


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


@pytest.mark.django_db
def test_unseen_observations_respect_the_area_filter(observations_and_areas):
    """An alert scoped to an area only marks observations inside it as unseen."""
    from django.contrib.auth import get_user_model

    from dashboard.models import Alert, ObservationUnseen, create_unseen_observations

    user = get_user_model().objects.create_user(
        username="u", password="p", email="u@e.com", notification_delay_days=365
    )
    alert = Alert.objects.create(
        name="Square only", user=user, email_notifications_frequency="N"
    )
    alert.species.set(Species.objects.all())
    alert.areas.set([observations_and_areas["square"]])

    create_unseen_observations(Observation.objects.all())

    unseen_ids = set(
        ObservationUnseen.objects.filter(user=user).values_list(
            "observation_id", flat=True
        )
    )
    # The parts-based filter reaches alert results too, so the border
    # observation is now marked unseen where ST_Within used to skip it. That is
    # the documented semantics change, asserted here rather than tolerated.
    on_border = Observation.objects.get(occurrence_id="1").pk
    expected = _old_filter_ids([observations_and_areas["square"].pk]) | {on_border}
    assert unseen_ids == expected
