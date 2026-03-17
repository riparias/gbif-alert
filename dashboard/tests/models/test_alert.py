import datetime

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import (
    Area,
    User,
    Alert,
    BasisOfRecord,
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationUnseen,
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

        cls.basis_of_record = BasisOfRecord.objects.create(
            name="HUMAN_OBSERVATION"
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
            basis_of_record=cls.basis_of_record,
        )

        # At the beginning of test_* methods, the observation is unseen
        cls.obs_unseen = ObservationUnseen.objects.create(
            observation=cls.observation, user=cls.user
        )

    def test_unseen_observations_count_one(self):
        """There's one unseen observation (same data as test_has_unseen_observations_true())"""
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertEqual(alert.unseen_observations_count, 1)

    def test_unseen_observations_count_zero_case_1(self):
        # The observation matches the alert, but has already been seen
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.obs_unseen.delete()
        self.assertEqual(alert.unseen_observations_count, 0)

    def test_unseen_observations_count_zero_case_2(self):
        # The observation is unseen, but doesn't match the alert
        another_species = Species.objects.create(
            name="Lixus Bardanae", gbif_taxon_key=48435
        )
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )
        alert.species.add(another_species)
        self.assertEqual(alert.unseen_observations_count, 0)

    def test_has_unseen_observations_true(self):
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertTrue(alert.has_unseen_observations)

    def test_has_unseen_observations_false_case_1(self):
        # The observation matches the alert, but has already been seen
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.obs_unseen.delete()
        self.assertFalse(alert.has_unseen_observations)

    def test_has_unseen_observations_false_case_2(self):
        # The observation is unseen, but doesn't match the alert
        another_species = Species.objects.create(
            name="Lixus Bardanae", gbif_taxon_key=48435
        )
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )
        alert.species.add(another_species)
        self.assertFalse(alert.has_unseen_observations)

    def test_basis_of_record_list_empty(self):
        """basis_of_record_list returns an empty string when no filters are set"""
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        self.assertEqual(alert.basis_of_record_list, "")

    def test_basis_of_record_list(self):
        """basis_of_record_list returns a comma-separated list of basis of record names"""
        alert = Alert.objects.create(
            user=self.user,
            name="BOR test alert",
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )
        bor2 = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
        alert.basis_of_record_filters.add(self.basis_of_record, bor2)
        self.assertEqual(
            alert.basis_of_record_list, "HUMAN_OBSERVATION, MACHINE_OBSERVATION"
        )

    def test_email_should_be_sent_now_no_notifications(self):
        """When the alert is configured for no emails, it's never a good time for notifications"""

        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.NO_EMAILS
        )

        # Situation:
        # - There is one unseen observation
        # - The alert matches every obs (including the unseen one)
        # - The alert has not previously sent emails
        #
        # => The only reason it's not a good time to send an email is because the user asked for no emails
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_nothing_unseen(self):
        """When nothing is unseen, it's not a good time for notifications"""

        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )

        self.obs_unseen.delete()

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
                user=self.user,
                email_notifications_frequency=frequency,
            )
            self.assertTrue(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_daily_too_early(self):
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(hours=16),
        )
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_daily(self):
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(hours=26),
        )
        self.assertTrue(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_weekly_too_early(self):
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.WEEKLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=6),
        )
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_weekly(self):
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.WEEKLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=8),
        )
        self.assertTrue(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_monthly_too_early(self):
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.MONTHLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=25),
        )
        self.assertFalse(alert.email_should_be_sent_now())

    def test_email_should_be_sent_now_montly(self):
        alert = Alert.objects.create(
            user=self.user,
            email_notifications_frequency=Alert.MONTHLY_EMAILS,
            last_email_sent_on=timezone.now() - datetime.timedelta(days=32),
        )
        self.assertTrue(alert.email_should_be_sent_now())


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class AlertCleanValidationTests(TestCase):
    """Unit tests for Alert.clean() validation of area_filter_mode / approaching_distance_km."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="clean_test_user",
            password="pass",
            email="clean@test.com",
        )

    def _make_alert(self, mode, distance_km):
        return Alert(
            user=self.user,
            area_filter_mode=mode,
            approaching_distance_km=distance_km,
        )

    def test_inside_with_no_distance_is_valid(self):
        alert = self._make_alert(Alert.AREA_FILTER_INSIDE, None)
        alert.clean()  # no exception

    def test_inside_with_distance_raises(self):
        alert = self._make_alert(Alert.AREA_FILTER_INSIDE, 10.0)
        with self.assertRaises(ValidationError) as ctx:
            alert.clean()
        self.assertIn("approaching_distance_km", ctx.exception.message_dict)

    def test_approaching_with_no_distance_raises(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, None)
        with self.assertRaises(ValidationError) as ctx:
            alert.clean()
        self.assertIn("approaching_distance_km", ctx.exception.message_dict)

    def test_approaching_with_zero_distance_raises(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, 0.0)
        with self.assertRaises(ValidationError) as ctx:
            alert.clean()
        self.assertIn("approaching_distance_km", ctx.exception.message_dict)

    def test_approaching_with_negative_distance_raises(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, -5.0)
        with self.assertRaises(ValidationError) as ctx:
            alert.clean()
        self.assertIn("approaching_distance_km", ctx.exception.message_dict)

    def test_approaching_with_distance_exceeding_max_raises(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, 51.0)
        with self.assertRaises(ValidationError) as ctx:
            alert.clean()
        self.assertIn("approaching_distance_km", ctx.exception.message_dict)

    def test_approaching_with_valid_distance_is_valid(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, 10.0)
        alert.clean()  # no exception

    def test_both_with_valid_distance_is_valid(self):
        alert = self._make_alert(Alert.AREA_FILTER_BOTH, 50.0)
        alert.clean()  # no exception

    def test_both_with_no_distance_raises(self):
        alert = self._make_alert(Alert.AREA_FILTER_BOTH, None)
        with self.assertRaises(ValidationError) as ctx:
            alert.clean()
        self.assertIn("approaching_distance_km", ctx.exception.message_dict)

    def test_approaching_with_max_distance_is_valid(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, 50.0)
        alert.clean()  # no exception


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class AlertAreaDescriptionTests(TestCase):
    """Unit tests for Alert.area_description property."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="desc_test_user",
            password="pass",
            email="desc@test.com",
        )
        cls.area_a = Area.objects.create(
            name="Foret de Soignes",
            mpoly=MultiPolygon(
                Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
                srid=4326,
            ),
        )
        cls.area_b = Area.objects.create(
            name="Zonienwoud",
            mpoly=MultiPolygon(
                Polygon(((4.4, 50.6), (4.5, 50.6), (4.5, 50.7), (4.4, 50.7), (4.4, 50.6))),
                srid=4326,
            ),
        )

    _counter = 0

    def _make_alert(self, mode, distance_km, areas):
        AlertAreaDescriptionTests._counter += 1
        alert = Alert.objects.create(
            user=self.user,
            name=f"desc_alert_{self._counter}",
            area_filter_mode=mode,
            approaching_distance_km=distance_km,
        )
        for area in areas:
            alert.areas.add(area)
        return alert

    def test_inside_single_area(self):
        alert = self._make_alert(Alert.AREA_FILTER_INSIDE, None, [self.area_a])
        self.assertEqual(alert.area_description, "inside 'Foret de Soignes'")

    def test_inside_two_areas(self):
        alert = self._make_alert(Alert.AREA_FILTER_INSIDE, None, [self.area_a, self.area_b])
        # Areas are ordered by name
        self.assertEqual(alert.area_description, "inside 'Foret de Soignes' or 'Zonienwoud'")

    def test_approaching_single_area(self):
        alert = self._make_alert(Alert.AREA_FILTER_APPROACHING, 10.0, [self.area_a])
        self.assertEqual(alert.area_description, "within 10 km of 'Foret de Soignes'")

    def test_both_single_area(self):
        alert = self._make_alert(Alert.AREA_FILTER_BOTH, 10.0, [self.area_a])
        self.assertEqual(alert.area_description, "inside or within 10 km of 'Foret de Soignes'")

    def test_no_areas_returns_empty_string(self):
        alert = self._make_alert(Alert.AREA_FILTER_INSIDE, None, [])
        self.assertEqual(alert.area_description, "")
