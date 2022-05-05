import datetime

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
)

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
                name="Procambarus fallax", gbif_taxon_key=8879526, group="CR"
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

    def test_has_alerts_with_unseen_observations_false_no_alerts(self):
        """The user has no alerts, so this should be false"""
        self.assertFalse(self.__class__.jason.has_alerts_with_unseen_observations)

    def test_has_alerts_with_unseen_observations_true(self):
        """The user has an alert with an unseen observation"""
        Alert.objects.create(
            user=self.__class__.jason, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertTrue(self.__class__.jason.has_alerts_with_unseen_observations)

    def test_has_alerts_with_unseen_observations_false_already_seen(self):
        """The user has an alert, but all the observations have already been seen"""
        Alert.objects.create(
            user=self.__class__.jason, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        ObservationView.objects.create(
            observation=self.__class__.observation, user=self.__class__.jason
        )

        self.assertFalse(self.__class__.jason.has_alerts_with_unseen_observations)

    def test_has_alert_with_unseen_observations_false_no_match(self):
        """The user has one unseen observation, but it doesn't match the alert"""
        another_species = Species.objects.create(
            name="Lixus Bardanae", gbif_taxon_key=48435, group="CR"
        )
        alert = Alert.objects.create(
            user=self.__class__.jason, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        alert.species.add(another_species)

        self.assertFalse(self.__class__.jason.has_alerts_with_unseen_observations)
