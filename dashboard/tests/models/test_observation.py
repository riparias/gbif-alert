import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import (
    Area,
    BasisOfRecord,
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationComment,
    ObservationUnseen,
    Alert,
    create_unseen_observations,
)

SAMPLE_DATASET_KEY = "940821c0-3269-11df-855a-b8a03c50a862"
SAMPLE_OCCURRENCE_ID = "BR:IFBL: 00494798"


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class ObservationTests(TestCase):
    def setUp(self):
        # Not possible to replace this by setUpTestData because some methods alter the observation => this code should
        # therefore be run before each method
        self.basis_of_record = BasisOfRecord.objects.create(
            name="HUMAN_OBSERVATION"
        )

        self.dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY
        )

        species_p_fallax = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )

        di = DataImport.objects.create(start=timezone.now())
        self.obs = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=species_p_fallax,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        User = get_user_model()
        self.comment_author = User.objects.create_user(
            username="testuser",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
            notification_delay_days=365,  # 1 year, the default value
        )

        # comment_author has also an alert that match second_obs
        self.alert = Alert.objects.create(
            user=self.comment_author,
        )
        self.alert.datasets.add(self.dataset)

        self.first_comment = ObservationComment.objects.create(
            author=self.comment_author,
            observation=self.obs,
            text="This is a first comment",
        )

        self.second_comment = ObservationComment.objects.create(
            author=self.comment_author,
            observation=self.obs,
            text="This is a second comment",
        )

        self.second_obs = Observation.objects.create(
            gbif_id=2,
            occurrence_id=123456,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        self.obs2_unseen_obj = ObservationUnseen.objects.create(
            observation=self.second_obs, user=self.comment_author
        )

    def test_as_dict_observation_seen_anonymous(self):
        """The as_dict() method does not contain observation_view data for anonymous users"""
        with self.assertRaises(KeyError):
            self.obs.as_dict(for_user=AnonymousUser())["seenByCurrentUser"]

    def test_as_dict_observation_seen_non_anonymous(self):
        """The as_dict() method contains observation_view data for authenticated users"""

        self.assertTrue(
            self.obs.as_dict(for_user=self.comment_author)["seenByCurrentUser"]
        )
        self.assertFalse(
            self.second_obs.as_dict(for_user=self.comment_author)["seenByCurrentUser"]
        )

    def test_already_seen_by_case_1(self):
        """Observation.already_seen_by() works as expected when the observation has been seen"""

        self.assertTrue(self.obs.already_seen_by(user=self.comment_author))

    def test_already_seen_by_case_2(self):
        """Observation.already_seen_by returns False if an observation has not been seen"""
        self.assertFalse(self.second_obs.already_seen_by(user=self.comment_author))

    def test_already_seen_by_case_3(self):
        """Observation.already_seen_by() returns None for anonymous users"""
        self.assertIsNone(self.obs.already_seen_by(user=AnonymousUser()))
        self.assertIsNone(self.second_obs.already_seen_by(user=AnonymousUser()))

    def test_mark_as_seen_by_case_1(self):
        """Standard case: we mark a previously unseen observation by a regular user"""
        # Before we start, we have an entry to confirm the observation is unseen
        self.assertEqual(
            ObservationUnseen.objects.filter(
                observation=self.second_obs, user=self.comment_author
            ).count(),
            1,
        )
        r = self.second_obs.mark_as_seen_by(user=self.comment_author)
        self.assertIsNone(r)  # Method always return None
        # After, we have don't have the unseen entry anymore
        self.assertEqual(
            ObservationUnseen.objects.filter(
                observation=self.second_obs, user=self.comment_author
            ).count(),
            0,
        )

    def test_mark_as_seen_by_case_2(self):
        """The user is anonymous: nothing happens"""
        self.assertEqual(
            ObservationUnseen.objects.filter(observation=self.second_obs).count(), 1
        )
        r = self.second_obs.mark_as_seen_by(user=AnonymousUser())
        self.assertIsNone(r)  # Method always return None
        # Nothing has changed:
        self.assertEqual(
            ObservationUnseen.objects.filter(observation=self.second_obs).count(), 1
        )

    def test_mark_as_seen_by_case_3(self):
        """The user has already seen this observation: nothing happens"""
        ovs_before = ObservationUnseen.objects.filter(observation=self.obs).values()
        r = self.second_obs.mark_as_seen_by(user=self.comment_author)
        self.assertIsNone(r)  # Method always return None

        ovs_after = ObservationUnseen.objects.filter(observation=self.obs).values()
        self.assertQuerysetEqual(ovs_after, ovs_before)

    def test_mark_as_unseen_by_happy_path(self):
        """Normal case: the user has previously seen the occurrence and it matches one
        of its users alerts"""

        # Situation before check
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(
                observation=self.obs, user=self.comment_author
            )
        self.assertTrue(self.comment_author.obs_match_alerts(self.obs))

        r = self.obs.mark_as_unseen_by(user=self.comment_author)
        self.assertTrue(r)
        # After, we can find it
        ObservationUnseen.objects.get(observation=self.obs, user=self.comment_author)

    def test_mark_as_unseen_by_failure_1(self):
        """Anonymous user: nothing happens and the method return False"""
        all_ous_before = ObservationUnseen.objects.all().values()
        r = self.obs.mark_as_unseen_by(user=AnonymousUser())
        self.assertFalse(r)
        all_ous_after = ObservationUnseen.objects.all().values()
        self.assertQuerysetEqual(all_ous_after, all_ous_before)

    def test_mark_as_unseen_by_failure_2(self):
        """User has not seen the observation before: method returns False, nothing happens to the db"""
        all_ous_before = ObservationUnseen.objects.all().values()
        r = self.second_obs.mark_as_unseen_by(user=self.comment_author)
        self.assertFalse(r)
        all_ous_after = ObservationUnseen.objects.all().values()
        self.assertQuerysetEqual(all_ous_after, all_ous_before)

    def test_mark_as_unseen_by_failure_3(self):
        """The user has seen the observation, but it doesn't match any of its alerts"""
        # We do the same thing that the happy path test, but we remove the alert first
        # Situation before check
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(
                observation=self.obs, user=self.comment_author
            )
        self.assertTrue(self.comment_author.obs_match_alerts(self.obs))

        self.alert.delete()

        r = self.obs.mark_as_unseen_by(user=self.comment_author)
        self.assertFalse(r)
        # There's still no unseen entry
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(
                observation=self.obs, user=self.comment_author
            )

    def test_date_older_than_user_delay(self):
        """The method works as expected"""
        yesterday = datetime.date.today() - datetime.timedelta(days=1)

        self.assertFalse(
            self.obs.date_older_than_user_delay(self.comment_author, the_date=yesterday)
        )

        two_years_ago = datetime.date.today() - datetime.timedelta(days=365 * 2)
        self.assertTrue(
            self.obs.date_older_than_user_delay(
                self.comment_author, the_date=two_years_ago
            )
        )

    def test_get_identical_observations_unsaved(self):
        """Regression test: the get_identical_observations() method also works with 'not yet saved' observations"""
        # Case 1: there's initially no identical observations in the database
        self.assertEqual(self.obs.get_identical_observations().count(), 0)

        new_di = DataImport.objects.create(start=timezone.now())
        new_one = Observation(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=new_di,
            initial_data_import=new_di,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        self.assertEqual(new_one.get_identical_observations().count(), 1)

    def test_get_identical_observations(self):
        # Case 1: there's initially no identical observations in the database
        self.assertEqual(self.obs.get_identical_observations().count(), 0)

        # Case 2: let's create a second one, but with a different stable_id (so the result should stay the same)
        di_2 = DataImport.objects.create(start=timezone.now())
        unrelated_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID[::-1],
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di_2,
            initial_data_import=di_2,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )
        self.assertEqual(self.obs.get_identical_observations().count(), 0)
        # Ensure the new one also has no identical
        self.assertEqual(unrelated_one.get_identical_observations().count(), 0)

        # Case 3: let's create a second, identical one
        di_3 = DataImport.objects.create(start=timezone.now())
        new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di_3,
            initial_data_import=di_3,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        # Test that we can access find the other one from any of the objects
        self.assertEqual(self.obs.get_identical_observations().count(), 1)
        self.assertEqual(self.obs.get_identical_observations()[0], new_one)

        self.assertEqual(new_one.get_identical_observations().count(), 1)
        self.assertEqual(new_one.get_identical_observations()[0], self.obs)

        # Case 4: Let's add a second identical
        di_4 = DataImport.objects.create(start=timezone.now())
        another_new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di_4,
            initial_data_import=di_4,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        self.assertEqual(self.obs.get_identical_observations().count(), 2)
        self.assertEqual(another_new_one.get_identical_observations().count(), 2)
        self.assertEqual(new_one.get_identical_observations().count(), 2)

        # Last check that the unrelated one is still isolated
        self.assertEqual(unrelated_one.get_identical_observations().count(), 0)

    def test_replaced_observations(self):
        # Case 1: initially, there's just a new observation in the database, nothing to be replaced
        self.assertIsNone(self.obs.replaced_observation)

        # Case 2: we add a second one to replace it
        di_2 = DataImport.objects.create(start=timezone.now())
        new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di_2,
            initial_data_import=di_2,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        # we can get the old one from the new one
        self.assertEqual(new_one.replaced_observation, self.obs)
        # That's not possible from the other side
        del self.obs.replaced_observation
        with self.assertRaises(Observation.OtherIdenticalObservationIsNewer):
            self.obs.replaced_observation

        # Case 3: we add a third one (that situation shouldn't happen in the real world, since each import replace
        # previous observations)
        di_3 = DataImport.objects.create(start=timezone.now())
        another_new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di_3,
            initial_data_import=di_3,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=self.basis_of_record,
        )

        # The three of them now report the inconsistency
        del new_one.replaced_observation
        with self.assertRaises(Observation.MultipleObjectsReturned):
            new_one.replaced_observation

        with self.assertRaises(Observation.MultipleObjectsReturned):
            another_new_one.replaced_observation

        with self.assertRaises(Observation.MultipleObjectsReturned):
            self.obs.replaced_observation


# A small square polygon in Belgium (roughly Lillois suburb area).
# Approx 7 km wide x 11 km tall.
_TEST_AREA_POLYGON = MultiPolygon(
    Polygon(
        ((4.30, 50.80), (4.40, 50.80), (4.40, 50.90), (4.30, 50.90), (4.30, 50.80)),
        srid=4326,
    ),
    srid=4326,
)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class AreaFilterModeTests(TestCase):
    """Integration tests for filtered_from_my_params() with area_filter_mode.

    Three observations are placed relative to _TEST_AREA_POLYGON:
    - obs_inside  : (4.35, 50.85) - clearly inside the polygon
    - obs_near    : (4.18, 50.85) - ~8.4 km west of the western edge, NOT inside
    - obs_far     : (3.50, 50.85) - ~56 km west, well outside any reasonable buffer
    """

    @classmethod
    def setUpTestData(cls):
        cls.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION_AFM")
        cls.species = Species.objects.create(
            name="Testus spatialis", gbif_taxon_key=9999001
        )
        cls.dataset = Dataset.objects.create(
            name="Spatial test dataset",
            gbif_dataset_key="aaaabbbb-0000-1111-2222-333344445555",
        )
        di = DataImport.objects.create(start=timezone.now())

        cls.area = Area.objects.create(name="Test square", mpoly=_TEST_AREA_POLYGON)

        cls.obs_inside = Observation.objects.create(
            gbif_id=9100,
            occurrence_id="afm_inside",
            species=cls.species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=cls.dataset,
            location=Point(4.35, 50.85, srid=4326),
            basis_of_record=cls.basis_of_record,
        )
        cls.obs_near = Observation.objects.create(
            gbif_id=9101,
            occurrence_id="afm_near",
            species=cls.species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=cls.dataset,
            location=Point(4.18, 50.85, srid=4326),  # ~8.4 km west of western edge
            basis_of_record=cls.basis_of_record,
        )
        cls.obs_far = Observation.objects.create(
            gbif_id=9102,
            occurrence_id="afm_far",
            species=cls.species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=cls.dataset,
            location=Point(3.50, 50.85, srid=4326),  # ~56 km west
            basis_of_record=cls.basis_of_record,
        )

    def _filter(self, mode, distance_km=None):
        return set(
            Observation.objects.filtered_from_my_params(
                species_ids=[self.species.pk],
                datasets_ids=[],
                basis_of_record_ids=[],
                start_date=None,
                end_date=None,
                areas_ids=[self.area.pk],
                status_for_user=None,
                initial_data_import_ids=[],
                user=None,
                area_filter_mode=mode,
                approaching_distance_km=distance_km,
            ).values_list("pk", flat=True)
        )

    def test_inside_mode_returns_only_observation_inside_polygon(self):
        result = self._filter("inside")
        self.assertIn(self.obs_inside.pk, result)
        self.assertNotIn(self.obs_near.pk, result)
        self.assertNotIn(self.obs_far.pk, result)

    def test_approaching_mode_excludes_inside_includes_nearby(self):
        """10 km buffer: obs_near (~8.4 km) is included; obs_inside is excluded."""
        result = self._filter("approaching", distance_km=10.0)
        self.assertNotIn(self.obs_inside.pk, result)
        self.assertIn(self.obs_near.pk, result)
        self.assertNotIn(self.obs_far.pk, result)

    def test_both_mode_includes_inside_and_nearby(self):
        result = self._filter("both", distance_km=10.0)
        self.assertIn(self.obs_inside.pk, result)
        self.assertIn(self.obs_near.pk, result)
        self.assertNotIn(self.obs_far.pk, result)

    def test_approaching_mode_small_buffer_excludes_everything(self):
        """1 km buffer: obs_near at ~8.4 km is too far away."""
        result = self._filter("approaching", distance_km=1.0)
        self.assertNotIn(self.obs_inside.pk, result)
        self.assertNotIn(self.obs_near.pk, result)
        self.assertNotIn(self.obs_far.pk, result)

    def test_inside_mode_is_default_when_no_distance_given(self):
        """When mode is 'approaching' but no distance_km, falls back to inside."""
        result = self._filter("approaching", distance_km=None)
        self.assertIn(self.obs_inside.pk, result)
        self.assertNotIn(self.obs_near.pk, result)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class CreateUnseenObservationsAreaFilterModeTests(TestCase):
    """Tests for create_unseen_observations() with the new area_filter_mode field."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="afm_user",
            password="pass",
            email="afm@test.com",
            notification_delay_days=365,
        )
        cls.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBS_AFM2")
        cls.species = Species.objects.create(
            name="Testus unseenus", gbif_taxon_key=9999002
        )
        cls.dataset = Dataset.objects.create(
            name="Unseen test dataset",
            gbif_dataset_key="bbbbcccc-0000-1111-2222-333344445555",
        )
        di = DataImport.objects.create(start=timezone.now())

        cls.area = Area.objects.create(name="Unseen test square", mpoly=_TEST_AREA_POLYGON)

        cls.obs_inside = Observation.objects.create(
            gbif_id=9200,
            occurrence_id="cu_inside",
            species=cls.species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=cls.dataset,
            location=Point(4.35, 50.85, srid=4326),
            basis_of_record=cls.basis_of_record,
        )
        cls.obs_near = Observation.objects.create(
            gbif_id=9201,
            occurrence_id="cu_near",
            species=cls.species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=cls.dataset,
            location=Point(4.18, 50.85, srid=4326),
            basis_of_record=cls.basis_of_record,
        )
        cls.obs_far = Observation.objects.create(
            gbif_id=9202,
            occurrence_id="cu_far",
            species=cls.species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=cls.dataset,
            location=Point(3.50, 50.85, srid=4326),
            basis_of_record=cls.basis_of_record,
        )

    def _run_create_unseen(self):
        all_obs = Observation.objects.filter(
            pk__in=[self.obs_inside.pk, self.obs_near.pk, self.obs_far.pk]
        )
        create_unseen_observations(all_obs)

    def _unseen_pks(self):
        return set(
            ObservationUnseen.objects.filter(user=self.user).values_list(
                "observation_id", flat=True
            )
        )

    _alert_counter = 0

    def _make_alert(self, mode, distance_km=None):
        CreateUnseenObservationsAreaFilterModeTests._alert_counter += 1
        alert = Alert.objects.create(
            user=self.user,
            name=f"alert_{self._alert_counter}",
            area_filter_mode=mode,
            approaching_distance_km=distance_km,
        )
        alert.species.add(self.species)
        alert.areas.add(self.area)
        return alert

    def setUp(self):
        ObservationUnseen.objects.all().delete()
        Alert.objects.filter(user=self.user).delete()

    def test_inside_alert_marks_only_inside_observation_as_unseen(self):
        self._make_alert("inside")
        self._run_create_unseen()
        unseen = self._unseen_pks()
        self.assertIn(self.obs_inside.pk, unseen)
        self.assertNotIn(self.obs_near.pk, unseen)
        self.assertNotIn(self.obs_far.pk, unseen)

    def test_approaching_alert_marks_only_near_observation_as_unseen(self):
        self._make_alert("approaching", distance_km=10.0)
        self._run_create_unseen()
        unseen = self._unseen_pks()
        self.assertNotIn(self.obs_inside.pk, unseen)
        self.assertIn(self.obs_near.pk, unseen)
        self.assertNotIn(self.obs_far.pk, unseen)

    def test_both_alert_marks_inside_and_near_as_unseen(self):
        self._make_alert("both", distance_km=10.0)
        self._run_create_unseen()
        unseen = self._unseen_pks()
        self.assertIn(self.obs_inside.pk, unseen)
        self.assertIn(self.obs_near.pk, unseen)
        self.assertNotIn(self.obs_far.pk, unseen)

    def test_two_alerts_different_modes_both_handled(self):
        """User with one inside alert and one approaching alert: both obs get marked."""
        self._make_alert("inside")
        self._make_alert("approaching", distance_km=10.0)
        self._run_create_unseen()
        unseen = self._unseen_pks()
        self.assertIn(self.obs_inside.pk, unseen)
        self.assertIn(self.obs_near.pk, unseen)
        self.assertNotIn(self.obs_far.pk, unseen)
