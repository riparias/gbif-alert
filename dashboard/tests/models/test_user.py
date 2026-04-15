import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import (
    Alert,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
    User,
)
from page_fragments.models import PageFragment

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_static_files_storage(settings):
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


@pytest.fixture
def user_data():
    jason = User.objects.create_user(
        username="jasonlytle", password="am180",
        first_name="Jason", last_name="Lytle", email="jason@grandaddy.com",
    )
    di = DataImport.objects.create(start=timezone.now())
    source_dataset = Dataset.objects.create(
        name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    observation = Observation.objects.create(
        gbif_id=1, occurrence_id="1",
        species=Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526),
        date=SEPTEMBER_13_2021,
        data_import=di, initial_data_import=di,
        source_dataset=source_dataset,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    obs_unseen = ObservationUnseen.objects.create(observation=observation, user=jason)
    jasons_comment = ObservationComment.objects.create(
        observation=observation, author=jason, text="I love this observation!",
    )
    return {
        "jason": jason,
        "source_dataset": source_dataset,
        "observation": observation,
        "obs_unseen": obs_unseen,
        "jasons_comment": jasons_comment,
    }


def test_obs_match_alerts_no_alert(user_data):
    """The user has no alerts, so this should be false."""
    assert not user_data["jason"].obs_match_alerts(user_data["observation"])


def test_obs_match_alert_true(user_data):
    """The user has an alert that matches the observation."""
    alert = Alert.objects.create(user=user_data["jason"], email_notifications_frequency=Alert.DAILY_EMAILS)
    alert.species.add(user_data["observation"].species)
    assert user_data["jason"].obs_match_alerts(user_data["observation"])


def test_obs_match_alert_multiple(user_data):
    """The user has multiple alerts which match the observation."""
    alert = Alert.objects.create(
        user=user_data["jason"], email_notifications_frequency=Alert.DAILY_EMAILS, name="Test alert #1",
    )
    alert.species.add(user_data["observation"].species)
    another_alert = Alert.objects.create(
        user=user_data["jason"], email_notifications_frequency=Alert.DAILY_EMAILS, name="Test alert #2",
    )
    another_alert.datasets.add(user_data["source_dataset"])
    assert user_data["jason"].obs_match_alerts(user_data["observation"])


def test_has_alerts_with_unseen_observations_false_no_alerts(user_data):
    """The user has no alerts, so this should be false."""
    assert not user_data["jason"].has_alerts_with_unseen_observations


def test_has_alerts_with_unseen_observations_true(user_data):
    """The user has an alert with an unseen observation."""
    Alert.objects.create(user=user_data["jason"], email_notifications_frequency=Alert.DAILY_EMAILS)
    assert user_data["jason"].has_alerts_with_unseen_observations


def test_has_alerts_with_unseen_observations_false_already_seen(user_data):
    """The user has an alert, but all observations have already been seen."""
    Alert.objects.create(user=user_data["jason"], email_notifications_frequency=Alert.DAILY_EMAILS)
    user_data["obs_unseen"].delete()
    assert not user_data["jason"].has_alerts_with_unseen_observations


def test_has_alert_with_unseen_observations_false_no_match(user_data):
    """The user has one unseen observation, but it doesn't match the alert."""
    another_species = Species.objects.create(name="Lixus Bardanae", gbif_taxon_key=48435)
    alert = Alert.objects.create(user=user_data["jason"], email_notifications_frequency=Alert.DAILY_EMAILS)
    alert.species.add(another_species)
    assert not user_data["jason"].has_alerts_with_unseen_observations


def test_user_with_comments_deletion(user_data):
    """Deleting a user empties their comments."""
    jasons_comment = user_data["jasons_comment"]
    jason = user_data["jason"]
    assert jasons_comment.author == jason
    assert jasons_comment.text == "I love this observation!"
    assert not jasons_comment.emptied_because_author_deleted_account

    jason.delete()

    jasons_comment.refresh_from_db()
    assert jasons_comment.author is None
    assert jasons_comment.text == ""
    assert jasons_comment.emptied_because_author_deleted_account


def test_user_never_visited_news_page(user_data):
    """The user has never visited the news page, has_unseen_news should be True."""
    assert user_data["jason"].has_unseen_news


def test_user_visited_news_page_recent(user_data):
    """User visited after last update, has_unseen_news should be False."""
    mocked = datetime.datetime(2022, 2, 11, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
    with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
        f = PageFragment.objects.get(identifier="news_page_content")
        f.content = "New content"
        f.save()
    user_data["jason"].mark_news_as_visited_now()
    user_data["jason"].refresh_from_db()
    assert not user_data["jason"].has_unseen_news


def test_user_visited_news_page_old(user_data):
    """The last visit predates the last update, so has_unseen_news should be True."""
    mocked = datetime.datetime(2020, 2, 11, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
    with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
        user_data["jason"].mark_news_as_visited_now()
    f = PageFragment.objects.get(identifier="news_page_content")
    f.content = "New content"
    f.save()
    user_data["jason"].refresh_from_db()
    assert user_data["jason"].has_unseen_news
