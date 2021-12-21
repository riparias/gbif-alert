import datetime

from django.contrib.auth import get_user_model
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
        # Not possible to replace this by setUpTestData because some methods alter the occurrence => this code should
        # therefore be run before each method.
        self.dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY
        )

        self.occ = Observation.objects.create(
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
            observation=self.occ,
            text="This is a first comment",
        )

        self.second_comment = ObservationComment.objects.create(
            author=self.comment_author,
            observation=self.occ,
            text="This is a second comment",
        )

        self.observation_view = ObservationView.objects.create(
            occurrence=self.occ, user=self.comment_author
        )

    def test_replace_occurrence(self):
        """High-level test: after creating a new occurrence with the same stable_id, make sure we can migrate the
        linked entities then and then delete the initial occurrence"""

        # 2. Create a new one
        new_occurrence = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=self.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        old_observation = self.occ

        view_timestamp_before = self.observation_view.timestamp

        # Migrate entities
        new_occurrence.migrate_linked_entities()

        # Make sure the counts are correct
        self.assertEqual(new_occurrence.observationcomment_set.count(), 2)
        self.assertEqual(old_observation.observationcomment_set.count(), 0)
        self.assertEqual(new_occurrence.observationview_set.count(), 1)
        self.assertEqual(old_observation.observationview_set.count(), 0)

        # Make also sure the comments fields were not accidentally altered
        self.first_comment.refresh_from_db()
        self.assertEqual(self.first_comment.author, self.comment_author)
        self.assertEqual(self.first_comment.text, "This is a first comment")
        self.assertEqual(self.first_comment.observation_id, new_occurrence.pk)

        self.second_comment.refresh_from_db()
        self.assertEqual(self.second_comment.author, self.comment_author)
        self.assertEqual(self.second_comment.text, "This is a second comment")
        self.assertEqual(self.second_comment.observation_id, new_occurrence.pk)

        # Make sure the occurrenceview other fields (timestamp, user, ...) were not accidentally altered
        self.observation_view.refresh_from_db()
        self.assertEqual(self.observation_view.occurrence, new_occurrence)
        self.assertEqual(self.observation_view.user, self.comment_author)
        self.assertEqual(self.observation_view.timestamp, view_timestamp_before)

        # The old occurrence can be safely deleted
        old_observation.delete()

    def test_get_identical_occurrences(self):
        # Case 1: there's initially no identical occurrences in the database
        self.assertEqual(self.occ.get_identical_occurrences().count(), 0)

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
        self.assertEqual(self.occ.get_identical_occurrences().count(), 0)
        # Ensure the new one also has no identical
        self.assertEqual(unrelated_one.get_identical_occurrences().count(), 0)

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
        self.assertEqual(self.occ.get_identical_occurrences().count(), 1)
        self.assertEqual(self.occ.get_identical_occurrences()[0], new_one)

        self.assertEqual(new_one.get_identical_occurrences().count(), 1)
        self.assertEqual(new_one.get_identical_occurrences()[0], self.occ)

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

        self.assertEqual(self.occ.get_identical_occurrences().count(), 2)
        self.assertEqual(another_new_one.get_identical_occurrences().count(), 2)
        self.assertEqual(new_one.get_identical_occurrences().count(), 2)

        # Last check that the unrelated one is still isolated
        self.assertEqual(unrelated_one.get_identical_occurrences().count(), 0)

    def test_replaced_occurrences(self):
        # Case 1: initially, there's just a new occurrence in the database, nothing to be replaced
        self.assertIsNone(self.occ.replaced_occurrence)

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
        self.assertEqual(new_one.replaced_occurrence, self.occ)
        # That's not possible from the other side
        with self.assertRaises(Observation.OtherIdenticalOccurrenceIsNewer):
            self.occ.replaced_occurrence

        # Case 3: we add a third one (that situation shouldn't happen in the real world, since each import replace
        # previous occurrences)
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
            new_one.replaced_occurrence

        with self.assertRaises(Observation.MultipleObjectsReturned):
            another_new_one.replaced_occurrence

        with self.assertRaises(Observation.MultipleObjectsReturned):
            self.occ.replaced_occurrence
