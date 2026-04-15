import datetime

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ValidationError
from django.utils import timezone

from dashboard.models import (
    Area,
    Alert,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationUnseen,
    Species,
    User,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Shared settings override (replaces @override_settings on each class)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_static_files_storage(settings):
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


# ---------------------------------------------------------------------------
# AlertTests fixtures and tests
# ---------------------------------------------------------------------------

@pytest.fixture
def alert_data():
    user = User.objects.create_user(
        username="jasonlytle",
        password="am180",
        first_name="Jason",
        last_name="Lytle",
        email="jason@grandaddy.com",
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(start=timezone.now())
    observation = Observation.objects.create(
        gbif_id=1,
        occurrence_id="1",
        species=Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526),
        date=SEPTEMBER_13_2021,
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        ),
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs_unseen = ObservationUnseen.objects.create(observation=observation, user=user)
    return {
        "user": user,
        "basis_of_record": basis_of_record,
        "observation": observation,
        "obs_unseen": obs_unseen,
    }


def test_unseen_observations_count_one(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    assert alert.unseen_observations_count == 1


def test_unseen_observations_count_zero_case_1(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert_data["obs_unseen"].delete()
    assert alert.unseen_observations_count == 0


def test_unseen_observations_count_zero_case_2(alert_data):
    another_species = Species.objects.create(name="Lixus Bardanae", gbif_taxon_key=48435)
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(another_species)
    assert alert.unseen_observations_count == 0


def test_has_unseen_observations_true(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    assert alert.has_unseen_observations


def test_has_unseen_observations_false_case_1(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert_data["obs_unseen"].delete()
    assert not alert.has_unseen_observations


def test_has_unseen_observations_false_case_2(alert_data):
    another_species = Species.objects.create(name="Lixus Bardanae", gbif_taxon_key=48435)
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(another_species)
    assert not alert.has_unseen_observations


def test_basis_of_record_list_empty(alert_data):
    """basis_of_record_list returns an empty string when no filters are set."""
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    assert alert.basis_of_record_list == ""


def test_basis_of_record_list(alert_data):
    """basis_of_record_list returns a comma-separated list of basis of record names."""
    alert = Alert.objects.create(
        user=alert_data["user"],
        name="BOR test alert",
        email_notifications_frequency=Alert.DAILY_EMAILS,
    )
    bor2 = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
    alert.basis_of_record_filters.add(alert_data["basis_of_record"], bor2)
    assert alert.basis_of_record_list == "HUMAN_OBSERVATION, MACHINE_OBSERVATION"


def test_email_should_be_sent_now_no_notifications(alert_data):
    """When the alert is configured for no emails, it is never a good time."""
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.NO_EMAILS
    )
    assert not alert.email_should_be_sent_now()


def test_email_should_be_sent_now_nothing_unseen(alert_data):
    """When nothing is unseen, it is not a good time for notifications."""
    alert = Alert.objects.create(
        user=alert_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert_data["obs_unseen"].delete()
    assert not alert.email_should_be_sent_now()


def test_email_should_be_sent_now_first_time(alert_data):
    """If there are unseen observations and no emails sent yet, now is the right time."""
    for i, frequency in enumerate([
        Alert.DAILY_EMAILS, Alert.WEEKLY_EMAILS, Alert.MONTHLY_EMAILS
    ]):
        alert = Alert.objects.create(
            name=f"My new test alert #{i}",
            user=alert_data["user"],
            email_notifications_frequency=frequency,
        )
        assert alert.email_should_be_sent_now()


def test_email_should_be_sent_now_daily_too_early(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"],
        email_notifications_frequency=Alert.DAILY_EMAILS,
        last_email_sent_on=timezone.now() - datetime.timedelta(hours=16),
    )
    assert not alert.email_should_be_sent_now()


def test_email_should_be_sent_now_daily(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"],
        email_notifications_frequency=Alert.DAILY_EMAILS,
        last_email_sent_on=timezone.now() - datetime.timedelta(hours=26),
    )
    assert alert.email_should_be_sent_now()


def test_email_should_be_sent_now_weekly_too_early(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"],
        email_notifications_frequency=Alert.WEEKLY_EMAILS,
        last_email_sent_on=timezone.now() - datetime.timedelta(days=6),
    )
    assert not alert.email_should_be_sent_now()


def test_email_should_be_sent_now_weekly(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"],
        email_notifications_frequency=Alert.WEEKLY_EMAILS,
        last_email_sent_on=timezone.now() - datetime.timedelta(days=8),
    )
    assert alert.email_should_be_sent_now()


def test_email_should_be_sent_now_monthly_too_early(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"],
        email_notifications_frequency=Alert.MONTHLY_EMAILS,
        last_email_sent_on=timezone.now() - datetime.timedelta(days=25),
    )
    assert not alert.email_should_be_sent_now()


def test_email_should_be_sent_now_monthly(alert_data):
    alert = Alert.objects.create(
        user=alert_data["user"],
        email_notifications_frequency=Alert.MONTHLY_EMAILS,
        last_email_sent_on=timezone.now() - datetime.timedelta(days=32),
    )
    assert alert.email_should_be_sent_now()


# ---------------------------------------------------------------------------
# AlertCleanValidationTests
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_user():
    return User.objects.create_user(
        username="clean_test_user", password="pass", email="clean@test.com"
    )


def test_inside_with_no_distance_is_valid(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_INSIDE, approaching_distance_km=None)
    alert.clean()  # no exception


def test_inside_with_distance_raises(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_INSIDE, approaching_distance_km=10.0)
    with pytest.raises(ValidationError) as exc:
        alert.clean()
    assert "approaching_distance_km" in exc.value.message_dict


def test_approaching_with_no_distance_raises(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_APPROACHING, approaching_distance_km=None)
    with pytest.raises(ValidationError) as exc:
        alert.clean()
    assert "approaching_distance_km" in exc.value.message_dict


def test_approaching_with_zero_distance_raises(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_APPROACHING, approaching_distance_km=0.0)
    with pytest.raises(ValidationError) as exc:
        alert.clean()
    assert "approaching_distance_km" in exc.value.message_dict


def test_approaching_with_negative_distance_raises(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_APPROACHING, approaching_distance_km=-5.0)
    with pytest.raises(ValidationError) as exc:
        alert.clean()
    assert "approaching_distance_km" in exc.value.message_dict


def test_approaching_with_distance_exceeding_max_raises(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_APPROACHING, approaching_distance_km=51.0)
    with pytest.raises(ValidationError) as exc:
        alert.clean()
    assert "approaching_distance_km" in exc.value.message_dict


def test_approaching_with_valid_distance_is_valid(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_APPROACHING, approaching_distance_km=10.0)
    alert.clean()  # no exception


def test_both_with_valid_distance_is_valid(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_BOTH, approaching_distance_km=50.0)
    alert.clean()  # no exception


def test_both_with_no_distance_raises(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_BOTH, approaching_distance_km=None)
    with pytest.raises(ValidationError) as exc:
        alert.clean()
    assert "approaching_distance_km" in exc.value.message_dict


def test_approaching_with_max_distance_is_valid(clean_user):
    alert = Alert(user=clean_user, area_filter_mode=Alert.AREA_FILTER_APPROACHING, approaching_distance_km=50.0)
    alert.clean()  # no exception


# ---------------------------------------------------------------------------
# AlertAreaDescriptionTests
# ---------------------------------------------------------------------------

@pytest.fixture
def area_desc_data():
    user = User.objects.create_user(
        username="desc_test_user", password="pass", email="desc@test.com"
    )
    area_a = Area.objects.create(
        name="Foret de Soignes",
        mpoly=MultiPolygon(
            Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
            srid=4326,
        ),
    )
    area_b = Area.objects.create(
        name="Zonienwoud",
        mpoly=MultiPolygon(
            Polygon(((4.4, 50.6), (4.5, 50.6), (4.5, 50.7), (4.4, 50.7), (4.4, 50.6))),
            srid=4326,
        ),
    )
    return {"user": user, "area_a": area_a, "area_b": area_b}


@pytest.fixture
def make_area_alert(area_desc_data):
    """Factory fixture for AlertAreaDescriptionTests - returns a callable."""
    counter = [0]

    def _make(mode, distance_km, areas):
        counter[0] += 1
        alert = Alert.objects.create(
            user=area_desc_data["user"],
            name=f"desc_alert_{counter[0]}",
            area_filter_mode=mode,
            approaching_distance_km=distance_km,
        )
        for area in areas:
            alert.areas.add(area)
        return alert

    return _make


def test_inside_single_area(make_area_alert, area_desc_data):
    alert = make_area_alert(Alert.AREA_FILTER_INSIDE, None, [area_desc_data["area_a"]])
    assert alert.area_description == "inside 'Foret de Soignes'"


def test_inside_two_areas(make_area_alert, area_desc_data):
    alert = make_area_alert(
        Alert.AREA_FILTER_INSIDE, None, [area_desc_data["area_a"], area_desc_data["area_b"]]
    )
    assert alert.area_description == "inside 'Foret de Soignes' or 'Zonienwoud'"


def test_approaching_single_area(make_area_alert, area_desc_data):
    alert = make_area_alert(Alert.AREA_FILTER_APPROACHING, 10.0, [area_desc_data["area_a"]])
    assert alert.area_description == "within 10 km of 'Foret de Soignes'"


def test_both_single_area(make_area_alert, area_desc_data):
    alert = make_area_alert(Alert.AREA_FILTER_BOTH, 10.0, [area_desc_data["area_a"]])
    assert alert.area_description == "inside or within 10 km of 'Foret de Soignes'"


def test_no_areas_returns_empty_string(make_area_alert):
    alert = make_area_alert(Alert.AREA_FILTER_INSIDE, None, [])
    assert alert.area_description == ""
