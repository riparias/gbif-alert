import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.utils import timezone

from dashboard.models import (
    Alert,
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
    create_unseen_observations,
)

SAMPLE_DATASET_KEY = "940821c0-3269-11df-855a-b8a03c50a862"
SAMPLE_OCCURRENCE_ID = "BR:IFBL: 00494798"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_static_files_storage(settings):
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


# ---------------------------------------------------------------------------
# ObservationTests - per-test setup (was setUp)
# ---------------------------------------------------------------------------

@pytest.fixture
def obs_data():
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    dataset = Dataset.objects.create(name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY)
    species_p_fallax = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    di = DataImport.objects.create(start=timezone.now())
    obs = Observation.objects.create(
        gbif_id=1,
        occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=species_p_fallax,
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di,
        initial_data_import=di,
        source_dataset=dataset,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    User = get_user_model()
    comment_author = User.objects.create_user(
        username="testuser", password="12345",
        first_name="John", last_name="Frusciante",
        email="frusciante@gmail.com",
        notification_delay_days=365,
    )
    alert = Alert.objects.create(user=comment_author)
    alert.datasets.add(dataset)
    first_comment = ObservationComment.objects.create(
        author=comment_author, observation=obs, text="This is a first comment",
    )
    second_comment = ObservationComment.objects.create(
        author=comment_author, observation=obs, text="This is a second comment",
    )
    second_obs = Observation.objects.create(
        gbif_id=2,
        occurrence_id=123456,
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di,
        initial_data_import=di,
        source_dataset=dataset,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs2_unseen_obj = ObservationUnseen.objects.create(observation=second_obs, user=comment_author)
    return {
        "basis_of_record": basis_of_record,
        "dataset": dataset,
        "di": di,
        "obs": obs,
        "comment_author": comment_author,
        "alert": alert,
        "first_comment": first_comment,
        "second_comment": second_comment,
        "second_obs": second_obs,
        "obs2_unseen_obj": obs2_unseen_obj,
    }


def test_as_dict_observation_seen_anonymous(obs_data):
    """as_dict() does not contain observation_view data for anonymous users."""
    with pytest.raises(KeyError):
        obs_data["obs"].as_dict(for_user=AnonymousUser())["seenByCurrentUser"]


def test_as_dict_observation_seen_non_anonymous(obs_data):
    """as_dict() contains observation_view data for authenticated users."""
    assert obs_data["obs"].as_dict(for_user=obs_data["comment_author"])["seenByCurrentUser"]
    assert not obs_data["second_obs"].as_dict(for_user=obs_data["comment_author"])["seenByCurrentUser"]


def test_already_seen_by_case_1(obs_data):
    """already_seen_by() works when the observation has been seen."""
    assert obs_data["obs"].already_seen_by(user=obs_data["comment_author"])


def test_already_seen_by_case_2(obs_data):
    """already_seen_by returns False if an observation has not been seen."""
    assert not obs_data["second_obs"].already_seen_by(user=obs_data["comment_author"])


def test_already_seen_by_case_3(obs_data):
    """already_seen_by() returns None for anonymous users."""
    assert obs_data["obs"].already_seen_by(user=AnonymousUser()) is None
    assert obs_data["second_obs"].already_seen_by(user=AnonymousUser()) is None


def test_mark_as_seen_by_case_1(obs_data):
    """Standard case: mark a previously unseen observation by a regular user."""
    assert ObservationUnseen.objects.filter(
        observation=obs_data["second_obs"], user=obs_data["comment_author"]
    ).count() == 1
    r = obs_data["second_obs"].mark_as_seen_by(user=obs_data["comment_author"])
    assert r is None
    assert ObservationUnseen.objects.filter(
        observation=obs_data["second_obs"], user=obs_data["comment_author"]
    ).count() == 0


def test_mark_as_seen_by_case_2(obs_data):
    """Anonymous user: nothing happens."""
    assert ObservationUnseen.objects.filter(observation=obs_data["second_obs"]).count() == 1
    r = obs_data["second_obs"].mark_as_seen_by(user=AnonymousUser())
    assert r is None
    assert ObservationUnseen.objects.filter(observation=obs_data["second_obs"]).count() == 1


def test_mark_as_seen_by_case_3(obs_data):
    """The user has already seen this observation: nothing happens."""
    ovs_before = list(ObservationUnseen.objects.filter(observation=obs_data["obs"]).values())
    r = obs_data["second_obs"].mark_as_seen_by(user=obs_data["comment_author"])
    assert r is None
    ovs_after = list(ObservationUnseen.objects.filter(observation=obs_data["obs"]).values())
    assert ovs_after == ovs_before


def test_mark_as_unseen_by_happy_path(obs_data):
    """Normal case: user has previously seen the occurrence and it matches one of their alerts."""
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs_data["obs"], user=obs_data["comment_author"])
    assert obs_data["comment_author"].obs_match_alerts(obs_data["obs"])

    r = obs_data["obs"].mark_as_unseen_by(user=obs_data["comment_author"])
    assert r
    ObservationUnseen.objects.get(observation=obs_data["obs"], user=obs_data["comment_author"])


def test_mark_as_unseen_by_failure_1(obs_data):
    """Anonymous user: nothing happens, method returns False."""
    all_ous_before = list(ObservationUnseen.objects.all().values())
    r = obs_data["obs"].mark_as_unseen_by(user=AnonymousUser())
    assert not r
    assert list(ObservationUnseen.objects.all().values()) == all_ous_before


def test_mark_as_unseen_by_failure_2(obs_data):
    """User has not seen the observation before: returns False, nothing happens."""
    all_ous_before = list(ObservationUnseen.objects.all().values())
    r = obs_data["second_obs"].mark_as_unseen_by(user=obs_data["comment_author"])
    assert not r
    assert list(ObservationUnseen.objects.all().values()) == all_ous_before


def test_mark_as_unseen_by_failure_3(obs_data):
    """User has seen the observation but it doesn't match any of their alerts."""
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs_data["obs"], user=obs_data["comment_author"])
    assert obs_data["comment_author"].obs_match_alerts(obs_data["obs"])

    obs_data["alert"].delete()

    r = obs_data["obs"].mark_as_unseen_by(user=obs_data["comment_author"])
    assert not r
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs_data["obs"], user=obs_data["comment_author"])


def test_date_older_than_user_delay(obs_data):
    """date_older_than_user_delay works as expected."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    assert not obs_data["obs"].date_older_than_user_delay(obs_data["comment_author"], the_date=yesterday)

    two_years_ago = datetime.date.today() - datetime.timedelta(days=365 * 2)
    assert obs_data["obs"].date_older_than_user_delay(obs_data["comment_author"], the_date=two_years_ago)


def test_get_identical_observations_unsaved(obs_data):
    """get_identical_observations() also works with unsaved observations."""
    assert obs_data["obs"].get_identical_observations().count() == 0
    new_di = DataImport.objects.create(start=timezone.now())
    new_one = Observation(
        gbif_id=1,
        occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=new_di,
        initial_data_import=new_di,
        source_dataset=obs_data["dataset"],
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=obs_data["basis_of_record"],
    )
    assert new_one.get_identical_observations().count() == 1


def test_get_identical_observations(obs_data):
    assert obs_data["obs"].get_identical_observations().count() == 0

    di_2 = DataImport.objects.create(start=timezone.now())
    unrelated_one = Observation.objects.create(
        gbif_id=1, occurrence_id=SAMPLE_OCCURRENCE_ID[::-1],
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di_2, initial_data_import=di_2,
        source_dataset=obs_data["dataset"],
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=obs_data["basis_of_record"],
    )
    assert obs_data["obs"].get_identical_observations().count() == 0
    assert unrelated_one.get_identical_observations().count() == 0

    di_3 = DataImport.objects.create(start=timezone.now())
    new_one = Observation.objects.create(
        gbif_id=1, occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di_3, initial_data_import=di_3,
        source_dataset=obs_data["dataset"],
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=obs_data["basis_of_record"],
    )
    assert obs_data["obs"].get_identical_observations().count() == 1
    assert obs_data["obs"].get_identical_observations()[0] == new_one
    assert new_one.get_identical_observations().count() == 1
    assert new_one.get_identical_observations()[0] == obs_data["obs"]

    di_4 = DataImport.objects.create(start=timezone.now())
    another_new_one = Observation.objects.create(
        gbif_id=1, occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di_4, initial_data_import=di_4,
        source_dataset=obs_data["dataset"],
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=obs_data["basis_of_record"],
    )
    assert obs_data["obs"].get_identical_observations().count() == 2
    assert another_new_one.get_identical_observations().count() == 2
    assert new_one.get_identical_observations().count() == 2
    assert unrelated_one.get_identical_observations().count() == 0


def test_replaced_observations(obs_data):
    assert obs_data["obs"].replaced_observation is None

    di_2 = DataImport.objects.create(start=timezone.now())
    new_one = Observation.objects.create(
        gbif_id=1, occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di_2, initial_data_import=di_2,
        source_dataset=obs_data["dataset"],
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=obs_data["basis_of_record"],
    )
    assert new_one.replaced_observation == obs_data["obs"]
    del obs_data["obs"].replaced_observation
    with pytest.raises(Observation.OtherIdenticalObservationIsNewer):
        obs_data["obs"].replaced_observation

    di_3 = DataImport.objects.create(start=timezone.now())
    another_new_one = Observation.objects.create(
        gbif_id=1, occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=Species.objects.all()[0],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di_3, initial_data_import=di_3,
        source_dataset=obs_data["dataset"],
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=obs_data["basis_of_record"],
    )
    del new_one.replaced_observation
    with pytest.raises(Observation.MultipleObjectsReturned):
        new_one.replaced_observation
    with pytest.raises(Observation.MultipleObjectsReturned):
        another_new_one.replaced_observation
    with pytest.raises(Observation.MultipleObjectsReturned):
        obs_data["obs"].replaced_observation


# ---------------------------------------------------------------------------
# AreaFilterModeTests
# ---------------------------------------------------------------------------

_TEST_AREA_POLYGON = MultiPolygon(
    Polygon(
        ((4.30, 50.80), (4.40, 50.80), (4.40, 50.90), (4.30, 50.90), (4.30, 50.80)),
        srid=4326,
    ),
    srid=4326,
)


@pytest.fixture
def area_filter_data():
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION_AFM")
    species = Species.objects.create(name="Testus spatialis", gbif_taxon_key=9999001)
    dataset = Dataset.objects.create(
        name="Spatial test dataset",
        gbif_dataset_key="aaaabbbb-0000-1111-2222-333344445555",
    )
    di = DataImport.objects.create(start=timezone.now())
    area = Area.objects.create(name="Test square", mpoly=_TEST_AREA_POLYGON)
    obs_inside = Observation.objects.create(
        gbif_id=9100, occurrence_id="afm_inside", species=species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=dataset, location=Point(4.35, 50.85, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs_near = Observation.objects.create(
        gbif_id=9101, occurrence_id="afm_near", species=species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=dataset, location=Point(4.18, 50.85, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs_far = Observation.objects.create(
        gbif_id=9102, occurrence_id="afm_far", species=species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=dataset, location=Point(3.50, 50.85, srid=4326),
        basis_of_record=basis_of_record,
    )
    return {
        "species": species, "area": area,
        "obs_inside": obs_inside, "obs_near": obs_near, "obs_far": obs_far,
    }


def _filter_obs(species, area, mode, distance_km=None):
    return set(
        Observation.objects.filtered_from_my_params(
            species_ids=[species.pk], datasets_ids=[], basis_of_record_ids=[],
            start_date=None, end_date=None, areas_ids=[area.pk],
            status_for_user=None, initial_data_import_ids=[], user=None,
            area_filter_mode=mode, approaching_distance_km=distance_km,
        ).values_list("pk", flat=True)
    )


def test_inside_mode_returns_only_observation_inside_polygon(area_filter_data):
    result = _filter_obs(area_filter_data["species"], area_filter_data["area"], "inside")
    assert area_filter_data["obs_inside"].pk in result
    assert area_filter_data["obs_near"].pk not in result
    assert area_filter_data["obs_far"].pk not in result


def test_approaching_mode_excludes_inside_includes_nearby(area_filter_data):
    """10 km buffer: obs_near (~8.4 km) is included; obs_inside is excluded."""
    result = _filter_obs(area_filter_data["species"], area_filter_data["area"], "approaching", distance_km=10.0)
    assert area_filter_data["obs_inside"].pk not in result
    assert area_filter_data["obs_near"].pk in result
    assert area_filter_data["obs_far"].pk not in result


def test_both_mode_includes_inside_and_nearby(area_filter_data):
    result = _filter_obs(area_filter_data["species"], area_filter_data["area"], "both", distance_km=10.0)
    assert area_filter_data["obs_inside"].pk in result
    assert area_filter_data["obs_near"].pk in result
    assert area_filter_data["obs_far"].pk not in result


def test_approaching_mode_small_buffer_excludes_everything(area_filter_data):
    """1 km buffer: obs_near at ~8.4 km is too far away."""
    result = _filter_obs(area_filter_data["species"], area_filter_data["area"], "approaching", distance_km=1.0)
    assert area_filter_data["obs_inside"].pk not in result
    assert area_filter_data["obs_near"].pk not in result
    assert area_filter_data["obs_far"].pk not in result


def test_inside_mode_is_default_when_no_distance_given(area_filter_data):
    """When mode is 'approaching' but no distance_km, falls back to inside."""
    result = _filter_obs(area_filter_data["species"], area_filter_data["area"], "approaching", distance_km=None)
    assert area_filter_data["obs_inside"].pk in result
    assert area_filter_data["obs_near"].pk not in result


# ---------------------------------------------------------------------------
# CreateUnseenObservationsAreaFilterModeTests
# ---------------------------------------------------------------------------

@pytest.fixture
def unseen_afm_data():
    User = get_user_model()
    user = User.objects.create_user(
        username="afm_user", password="pass", email="afm@test.com", notification_delay_days=365,
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBS_AFM2")
    species = Species.objects.create(name="Testus unseenus", gbif_taxon_key=9999002)
    dataset = Dataset.objects.create(
        name="Unseen test dataset",
        gbif_dataset_key="bbbbcccc-0000-1111-2222-333344445555",
    )
    di = DataImport.objects.create(start=timezone.now())
    area = Area.objects.create(name="Unseen test square", mpoly=_TEST_AREA_POLYGON)
    obs_inside = Observation.objects.create(
        gbif_id=9200, occurrence_id="cu_inside", species=species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=dataset, location=Point(4.35, 50.85, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs_near = Observation.objects.create(
        gbif_id=9201, occurrence_id="cu_near", species=species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=dataset, location=Point(4.18, 50.85, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs_far = Observation.objects.create(
        gbif_id=9202, occurrence_id="cu_far", species=species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=dataset, location=Point(3.50, 50.85, srid=4326),
        basis_of_record=basis_of_record,
    )
    return {
        "user": user, "species": species, "area": area,
        "obs_inside": obs_inside, "obs_near": obs_near, "obs_far": obs_far,
    }


def _make_unseen_alert(user, species, area, mode, distance_km=None):
    import uuid
    alert = Alert.objects.create(
        user=user, name=f"alert_{uuid.uuid4().hex[:8]}",
        area_filter_mode=mode, approaching_distance_km=distance_km,
    )
    alert.species.add(species)
    alert.areas.add(area)
    return alert


def test_inside_alert_marks_only_inside_observation_as_unseen(unseen_afm_data):
    _make_unseen_alert(unseen_afm_data["user"], unseen_afm_data["species"], unseen_afm_data["area"], "inside")
    create_unseen_observations(
        Observation.objects.filter(pk__in=[
            unseen_afm_data["obs_inside"].pk,
            unseen_afm_data["obs_near"].pk,
            unseen_afm_data["obs_far"].pk,
        ])
    )
    unseen = set(ObservationUnseen.objects.filter(user=unseen_afm_data["user"]).values_list("observation_id", flat=True))
    assert unseen_afm_data["obs_inside"].pk in unseen
    assert unseen_afm_data["obs_near"].pk not in unseen
    assert unseen_afm_data["obs_far"].pk not in unseen


def test_approaching_alert_marks_only_near_observation_as_unseen(unseen_afm_data):
    _make_unseen_alert(unseen_afm_data["user"], unseen_afm_data["species"], unseen_afm_data["area"], "approaching", distance_km=10.0)
    create_unseen_observations(
        Observation.objects.filter(pk__in=[
            unseen_afm_data["obs_inside"].pk, unseen_afm_data["obs_near"].pk, unseen_afm_data["obs_far"].pk,
        ])
    )
    unseen = set(ObservationUnseen.objects.filter(user=unseen_afm_data["user"]).values_list("observation_id", flat=True))
    assert unseen_afm_data["obs_inside"].pk not in unseen
    assert unseen_afm_data["obs_near"].pk in unseen
    assert unseen_afm_data["obs_far"].pk not in unseen


def test_both_alert_marks_inside_and_near_as_unseen(unseen_afm_data):
    _make_unseen_alert(unseen_afm_data["user"], unseen_afm_data["species"], unseen_afm_data["area"], "both", distance_km=10.0)
    create_unseen_observations(
        Observation.objects.filter(pk__in=[
            unseen_afm_data["obs_inside"].pk, unseen_afm_data["obs_near"].pk, unseen_afm_data["obs_far"].pk,
        ])
    )
    unseen = set(ObservationUnseen.objects.filter(user=unseen_afm_data["user"]).values_list("observation_id", flat=True))
    assert unseen_afm_data["obs_inside"].pk in unseen
    assert unseen_afm_data["obs_near"].pk in unseen
    assert unseen_afm_data["obs_far"].pk not in unseen


def test_two_alerts_different_modes_both_handled(unseen_afm_data):
    """User with one inside alert and one approaching alert: both obs get marked."""
    _make_unseen_alert(unseen_afm_data["user"], unseen_afm_data["species"], unseen_afm_data["area"], "inside")
    _make_unseen_alert(unseen_afm_data["user"], unseen_afm_data["species"], unseen_afm_data["area"], "approaching", distance_km=10.0)
    create_unseen_observations(
        Observation.objects.filter(pk__in=[
            unseen_afm_data["obs_inside"].pk, unseen_afm_data["obs_near"].pk, unseen_afm_data["obs_far"].pk,
        ])
    )
    unseen = set(ObservationUnseen.objects.filter(user=unseen_afm_data["user"]).values_list("observation_id", flat=True))
    assert unseen_afm_data["obs_inside"].pk in unseen
    assert unseen_afm_data["obs_near"].pk in unseen
    assert unseen_afm_data["obs_far"].pk not in unseen
