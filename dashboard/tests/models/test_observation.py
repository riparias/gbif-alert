import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationComment,
    ObservationUnseen,
    Alert,
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

    def test_replace_observation(self):
        """High-level test: after creating a new observation with the same stable_id, make sure we can migrate the
        linked entities then and then delete the initial observation"""

        # 2. Create a new one
        new_di = DataImport.objects.create(start=timezone.now())
        new_observation = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=new_di,
            initial_data_import=new_di,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        old_observation = self.obs

        # Migrate entities
        new_observation.migrate_linked_entities()

        # Make sure the counts are correct
        self.assertEqual(new_observation.observationcomment_set.count(), 2)
        self.assertEqual(old_observation.observationcomment_set.count(), 0)

        # Make also sure the comments fields were not accidentally altered
        self.first_comment.refresh_from_db()
        self.assertEqual(self.first_comment.author, self.comment_author)
        self.assertEqual(self.first_comment.text, "This is a first comment")
        self.assertEqual(self.first_comment.observation_id, new_observation.pk)

        self.second_comment.refresh_from_db()
        self.assertEqual(self.second_comment.author, self.comment_author)
        self.assertEqual(self.second_comment.text, "This is a second comment")
        self.assertEqual(self.second_comment.observation_id, new_observation.pk)

        # The replaced observation was seen, so the new one should be seen too
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(
                observation=new_observation, user=self.comment_author
            )

        # The old observation can be safely deleted
        old_observation.delete()

    def test_replace_observation_unseen(self):
        """Similar to test_replace_observation, but the replaced observation was not seen

        (there was an entry in observationunseen. we make sure this entry now properly
        points to the new observation)(it is not automatically marked as seen because
        the user has a matching alert, and the observation is recent)
        """

        new_di = DataImport.objects.create(start=timezone.now())
        replacement_second_obs = Observation.objects.create(
            gbif_id=2,
            occurrence_id=123456,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=new_di,
            initial_data_import=new_di,
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        replacement_second_obs.migrate_linked_entities()
        self.obs2_unseen_obj.refresh_from_db()

        self.assertEqual(self.obs2_unseen_obj.observation, replacement_second_obs)

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
        )

        # The three of them now report the inconsistency
        del new_one.replaced_observation
        with self.assertRaises(Observation.MultipleObjectsReturned):
            new_one.replaced_observation

        with self.assertRaises(Observation.MultipleObjectsReturned):
            another_new_one.replaced_observation

        with self.assertRaises(Observation.MultipleObjectsReturned):
            self.obs.replaced_observation
