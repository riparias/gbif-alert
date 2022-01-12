import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationComment,
    ObservationView,
)

SAMPLE_DATASET_KEY = "940821c0-3269-11df-855a-b8a03c50a862"
SAMPLE_OCCURRENCE_ID = "BR:IFBL: 00494798"


class ObservationTests(TestCase):
    def setUp(self):
        # Not possible to replace this by setUpTestData because some methods alter the observation => this code should
        # therefore be run before each method
        self.dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY
        )

        self.obs = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
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
        )

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

        self.observation_view = ObservationView.objects.create(
            observation=self.obs, user=self.comment_author
        )

        self.second_obs = Observation.objects.create(
            gbif_id=2,
            occurrence_id=123456,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

    def test_as_dict_observation_view_anonymous(self):
        """The as_dict() method does not contain observation_view data for anonymous users"""
        with self.assertRaises(KeyError):
            self.obs.as_dict(for_user=AnonymousUser())["viewedByCurrentUser"]

    def test_as_dict_observation_view_non_anonymous(self):
        """The as_dict() method does not contain observation_view data for anonymous users"""

        self.assertTrue(
            self.obs.as_dict(for_user=self.comment_author)["viewedByCurrentUser"]
        )
        self.assertFalse(
            self.second_obs.as_dict(for_user=self.comment_author)["viewedByCurrentUser"]
        )

    def test_first_viewed_at_case_1(self):
        """Observation.first_viewed_at() works as expected when the observation has been seen"""
        now = timezone.now()
        timestamp = self.obs.first_viewed_at(user=self.comment_author)

        self.assertLess(now - timestamp, datetime.timedelta(minutes=1))

    def test_first_viewed_at_case_2(self):
        """Observation.first_viewed_at() returns None if an observation has not been seen"""
        self.assertIsNone(self.second_obs.first_viewed_at(user=self.comment_author))

    def test_first_viewed_at_case_3(self):
        """Observation.first_viewed_at() returns None for anonymous users"""
        self.assertIsNone(self.obs.first_viewed_at(user=AnonymousUser()))
        self.assertIsNone(self.second_obs.first_viewed_at(user=AnonymousUser()))

    def test_mark_as_viewed_by_case_1(self):
        """Standard case: a we mark a not views obs by a regular user"""
        # Before we start, we have no entry
        self.assertEqual(
            ObservationView.objects.filter(observation=self.second_obs).count(), 0
        )
        r = self.second_obs.mark_as_viewed_by(user=self.comment_author)
        self.assertIsNone(r)  # Method always return None
        # After, we have one entry
        ov = ObservationView.objects.get(observation=self.second_obs)

        # Basic checks on observationView objects
        self.assertEqual(ov.user.username, "testuser")
        self.assertEqual(ov.observation.id, self.second_obs.id)
        self.assertLess(timezone.now() - ov.timestamp, datetime.timedelta(minutes=1))

    def test_mark_as_viewed_by_case_2(self):
        """The user is anonymous: nothing happens"""
        self.assertEqual(
            ObservationView.objects.filter(observation=self.second_obs).count(), 0
        )
        r = self.second_obs.mark_as_viewed_by(user=AnonymousUser())
        self.assertIsNone(r)  # Method always return None
        # Nothing has changed:
        self.assertEqual(
            ObservationView.objects.filter(observation=self.second_obs).count(), 0
        )

    def test_mark_as_viewed_by_case_3(self):
        """The user has already seen this observation: nothing happens"""
        ovs_before = ObservationView.objects.filter(observation=self.obs).values()
        r = self.second_obs.mark_as_viewed_by(user=self.comment_author)
        self.assertIsNone(r)  # Method always return None

        ovs_after = ObservationView.objects.filter(observation=self.obs).values()
        self.assertQuerysetEqual(ovs_after, ovs_before)

    def test_mark_as_not_viewed_by_case_1(self):
        """Normal case: the user has indeed previously seen the occurrence"""
        # Before, we can find it
        ObservationView.objects.get(observation=self.obs, user=self.comment_author)
        r = self.obs.mark_as_not_viewed_by(user=self.comment_author)
        self.assertTrue(r)
        with self.assertRaises(ObservationView.DoesNotExist):
            ObservationView.objects.get(observation=self.obs, user=self.comment_author)

    def test_mark_as_not_viewed_by_case_2(self):
        """Anonymous user: nothing happens and the method return False"""
        all_ovs_before = ObservationView.objects.all().values()
        r = self.obs.mark_as_not_viewed_by(user=AnonymousUser())
        self.assertFalse(r)
        all_ovs_after = ObservationView.objects.all().values()
        self.assertQuerysetEqual(all_ovs_after, all_ovs_before)

    def test_mark_as_not_viewed_by_case_3(self):
        """User has not seen the observation before: method returns False, nothing happens to the db"""
        all_ovs_before = ObservationView.objects.all().values()
        r = self.second_obs.mark_as_not_viewed_by(user=self.comment_author)
        self.assertFalse(r)
        all_ovs_after = ObservationView.objects.all().values()
        self.assertQuerysetEqual(all_ovs_after, all_ovs_before)

    def test_replace_observation(self):
        """High-level test: after creating a new observation with the same stable_id, make sure we can migrate the
        linked entities then and then delete the initial observation"""

        # 2. Create a new one
        new_observation = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        old_observation = self.obs

        view_timestamp_before = self.observation_view.timestamp

        # Migrate entities
        new_observation.migrate_linked_entities()

        # Make sure the counts are correct
        self.assertEqual(new_observation.observationcomment_set.count(), 2)
        self.assertEqual(old_observation.observationcomment_set.count(), 0)
        self.assertEqual(new_observation.observationview_set.count(), 1)
        self.assertEqual(old_observation.observationview_set.count(), 0)

        # Make also sure the comments fields were not accidentally altered
        self.first_comment.refresh_from_db()
        self.assertEqual(self.first_comment.author, self.comment_author)
        self.assertEqual(self.first_comment.text, "This is a first comment")
        self.assertEqual(self.first_comment.observation_id, new_observation.pk)

        self.second_comment.refresh_from_db()
        self.assertEqual(self.second_comment.author, self.comment_author)
        self.assertEqual(self.second_comment.text, "This is a second comment")
        self.assertEqual(self.second_comment.observation_id, new_observation.pk)

        # Make sure the observation_view other fields (timestamp, user, ...) were not accidentally altered
        self.observation_view.refresh_from_db()
        self.assertEqual(self.observation_view.observation, new_observation)
        self.assertEqual(self.observation_view.user, self.comment_author)
        self.assertEqual(self.observation_view.timestamp, view_timestamp_before)

        # The old observation can be safely deleted
        old_observation.delete()

    def test_get_identical_observations(self):
        # Case 1: there's initially no identical observations in the database
        self.assertEqual(self.obs.get_identical_observations().count(), 0)

        # Case 2: let's create a second one, but with a different stable_id (so the result should stay the same)
        unrelated_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID[::-1],
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )
        self.assertEqual(self.obs.get_identical_observations().count(), 0)
        # Ensure the new one also has no identical
        self.assertEqual(unrelated_one.get_identical_observations().count(), 0)

        # Case 3: let's create a second, identical one
        new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        # Test that we can access find the other one from any of the objects
        self.assertEqual(self.obs.get_identical_observations().count(), 1)
        self.assertEqual(self.obs.get_identical_observations()[0], new_one)

        self.assertEqual(new_one.get_identical_observations().count(), 1)
        self.assertEqual(new_one.get_identical_observations()[0], self.obs)

        # Case 4: Let's add a second identical
        another_new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
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
        new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        # we can get the old one from the new one
        self.assertEqual(new_one.replaced_observation, self.obs)
        # That's not possible from the other side
        with self.assertRaises(Observation.OtherIdenticalObservationIsNewer):
            self.obs.replaced_observation

        # Case 3: we add a third one (that situation shouldn't happen in the real world, since each import replace
        # previous observations)
        another_new_one = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        # The three of them now report the inconsistency
        with self.assertRaises(Observation.MultipleObjectsReturned):
            new_one.replaced_observation

        with self.assertRaises(Observation.MultipleObjectsReturned):
            another_new_one.replaced_observation

        with self.assertRaises(Observation.MultipleObjectsReturned):
            self.obs.replaced_observation
