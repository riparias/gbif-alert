import datetime
from django.test import TestCase, override_settings

from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import (
    User,
    Alert,
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationView,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class AlertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
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

    def test_unseen_observations_count_one(self):
        """There's one unseen observation (same data as test_has_unseen_observations_true())"""
        alert = Alert.objects.create(
            user=self.__class__.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertEqual(alert.unseen_observations_count, 1)

    def test_unseen_observations_count_zero_case_1(self):
        # The observation matches the alert, but has already been seen
        alert = Alert.objects.create(
            user=self.__class__.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        ObservationView.objects.create(
            observation=self.__class__.observation, user=self.__class__.user
        )
        self.assertEqual(alert.unseen_observations_count, 0)

    def test_unseen_observations_count_zero_case_2(self):
        # The observation is unseen, but doesn't match the alert
        another_species = Species.objects.create(
            name="Lixus Bardanae", gbif_taxon_key=48435, group="CR"
        )
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )
        alert.species.add(another_species)
        self.assertEqual(alert.unseen_observations_count, 0)

    def test_has_unseen_observations_true(self):
        alert = Alert.objects.create(
            user=self.__class__.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertTrue(alert.has_unseen_observations)

    def test_has_unseen_observations_false_case_1(self):
        # The observation matches the alert, but has already been seen
        alert = Alert.objects.create(
            user=self.__class__.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        ObservationView.objects.create(
            observation=self.__class__.observation, user=self.__class__.user
        )
        self.assertFalse(alert.has_unseen_observations)

    def test_has_unseen_observations_false_case_2(self):
        # The observation is unseen, but doesn't match the alert
        another_species = Species.objects.create(
            name="Lixus Bardanae", gbif_taxon_key=48435, group="CR"
        )
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )
        alert.species.add(another_species)
        self.assertFalse(alert.has_unseen_observations)

    def test_email_should_be_sent_now_no_notifications(self):
        """When the alert is configured for no emails, it's never a good time for notifications"""

        alert = Alert.objects.create(
            user=self.__class__.user, email_notifications_frequency=Alert.NO_EMAILS
        )

        # Situation:
        # - There is one unseen observation
        # - The alert matches every obs (including the unseen one)
        # - The alert has not previously sent emails
        #
        # => The only reason it's not a good time to send an email is because the user asked for no emails
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_nothing_unseen(self):
        """When nothing is unseen, it's not a god time for notifications"""

        alert = Alert.objects.create(
            user=self.__class__.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )

        ObservationView.objects.create(
            observation=self.__class__.observation, user=self.__class__.user
        )

        # Situation:
        # - No unseen observation
        # - The alert matches every obs
        # - The alert is configured for (daily) notifications
        # - The alert has not previously sent emails
        # - The alert has not generated e-mail notifications yet
        #
        # => The only reason it's not a good time to send an email is because there's no unseen observation
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_first_time(self):
        """If there are unseen observation and no emails send yet, now is the good time for the first"""
        frequencies_to_be_checked = [
            Alert.DAILY_EMAILS,
            Alert.WEEKLY_EMAILS,
            Alert.MONTHLY_EMAILS,
        ]
        for i, frequency in enumerate(frequencies_to_be_checked):
            alert = Alert.objects.create(
                name=f"My new test alert #{i}",
                user=self.__class__.user,
                email_notifications_frequency=frequency,
            )
            self.assertTrue(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_daily_too_early(self):
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(hours=16),
        )
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_daily(self):
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(hours=26),
        )
        self.assertTrue(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_weekly_too_early(self):
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.WEEKLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=6),
        )
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_weekly(self):
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.WEEKLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=8),
        )
        self.assertTrue(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_monthly_too_early(self):
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.MONTHLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=25),
        )
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_montly(self):
        alert = Alert.objects.create(
            user=self.__class__.user,
            email_notifications_frequency=Alert.MONTHLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=32),
        )
        self.assertTrue(alert.email_should_be_sent_now())
