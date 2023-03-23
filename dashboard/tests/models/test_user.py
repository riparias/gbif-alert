import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import (
    User,
    DataImport,
    Observation,
    Species,
    Dataset,
    Alert,
    ObservationView,
    ObservationComment,
)
from page_fragments.models import PageFragment

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class UserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.jason = User.objects.create_user(
            username="jasonlytle",
            password="am180",
            first_name="Jason",
            last_name="Lytle",
            email="jason@grandaddy.com",
        )

        di = DataImport.objects.create(start=timezone.now())

        cls.observation = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=Species.objects.create(
                name="Procambarus fallax", gbif_taxon_key=8879526
            ),
            date=SEPTEMBER_13_2021,
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
            ),
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        # No ObservationView created in setupTestData(): at the beginning of test_* methods, the observation is unseen

        # The user has a comment on the observation, it should be emptied upon deletion
        cls.jasons_comment = ObservationComment.objects.create(
            observation=cls.observation,
            author=cls.jason,
            text="I love this observation!",
        )

    def test_has_alerts_with_unseen_observations_false_no_alerts(self):
        """The user has no alerts, so this should be false"""
        self.assertFalse(self.jason.has_alerts_with_unseen_observations)

    def test_has_alerts_with_unseen_observations_true(self):
        """The user has an alert with an unseen observation"""
        Alert.objects.create(
            user=self.jason, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertTrue(self.jason.has_alerts_with_unseen_observations)

    def test_has_alerts_with_unseen_observations_false_already_seen(self):
        """The user has an alert, but all the observations have already been seen"""
        Alert.objects.create(
            user=self.jason, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        ObservationView.objects.create(observation=self.observation, user=self.jason)

        self.assertFalse(self.jason.has_alerts_with_unseen_observations)

    def test_has_alert_with_unseen_observations_false_no_match(self):
        """The user has one unseen observation, but it doesn't match the alert"""
        another_species = Species.objects.create(
            name="Lixus Bardanae", gbif_taxon_key=48435
        )
        alert = Alert.objects.create(
            user=self.jason, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        alert.species.add(another_species)

        self.assertFalse(self.jason.has_alerts_with_unseen_observations)

    def test_user_with_comments_deletion(self):
        """The user has a comment on the observation, it should be emptied upon deletion"""
        # Let's check the initial situation
        self.assertEqual(self.jasons_comment.author, self.jason)
        self.assertEqual(self.jasons_comment.text, "I love this observation!")
        self.assertFalse(self.jasons_comment.emptied_because_author_deleted_account)

        self.jason.delete()  # This also indirectly checks that the user can be deleted even if it has comments

        # After deletion, the comment should be emptied
        self.jasons_comment.refresh_from_db()
        self.assertEqual(self.jasons_comment.author, None)
        self.assertEqual(self.jasons_comment.text, "")
        self.assertTrue(self.jasons_comment.emptied_because_author_deleted_account)

    def test_user_never_visited_news_page(self):
        """The user has never visited the news page, has_unseen_news should be True"""
        self.assertTrue(self.jason.has_unseen_news)

    def test_user_visited_news_page_recent(self):
        """The user has visited the news page after its last update, has_unseen_news should be False"""

        mocked = datetime.datetime(2022, 2, 11, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            f = PageFragment.objects.get(identifier="news_page_content")
            f.content = "New content"
            f.save()

        self.jason.mark_news_as_visited_now()

        self.jason.refresh_from_db()
        self.assertFalse(self.jason.has_unseen_news)

    def test_user_visited_news_page_old(self):
        """The last visit to the news page predates its last update, so has_unseen_news should be True"""

        mocked = datetime.datetime(2020, 2, 11, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            self.jason.mark_news_as_visited_now()

        f = PageFragment.objects.get(identifier="news_page_content")
        f.content = "New content"
        f.save()

        self.jason.refresh_from_db()
        self.assertTrue(self.jason.has_unseen_news)
