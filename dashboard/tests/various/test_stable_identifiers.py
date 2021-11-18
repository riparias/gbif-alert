import datetime
from django.test import TestCase

from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import Occurrence, Species, DataImport, Dataset

SAMPLE_DATASET_KEY = "940821c0-3269-11df-855a-b8a03c50a862"
SAMPLE_OCCURRENCE_ID = "BR:IFBL: 00494798"
EXPECTED_STABLE_ID = "e58dabf7bcc72dc6b3e057859ed89a453eea527d"


class StableIdentifiersTests(TestCase):
    def setUp(self):
        # Not possible to remplace this by setUpTestData because some methods alter the occurrence => this code should
        # therefore be run before each method.
        self.occ = Occurrence.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=Dataset.objects.create(
                name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY
            ),
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

    def test_stable_correct_value(self):
        """The stable identifier has the expected value and is therefore predictable over time"""
        self.assertEqual(self.occ.stable_id, EXPECTED_STABLE_ID)

    def test_follows_occurrence_id(self):
        """The stable identifier changes if the occurrence_id is updated"""
        stable_id_before = self.occ.stable_id
        self.occ.occurrence_id = "something new"
        self.occ.save()

        self.occ.refresh_from_db()  # Refresh is probably not necessary here, providing it for consistency with
        # test_follows_dataset_key()
        self.assertNotEqual(stable_id_before, self.occ.stable_id)

    def test_follows_dataset_key(self):
        """The stable identifier changes if the dataset key is updated

        Note: this won't probably happen in real-world use, but it's a good practice and add extra safety
        """
        stable_id_before = self.occ.stable_id
        self.occ.source_dataset.gbif_dataset_key = "something new"
        self.occ.source_dataset.save()

        self.occ.refresh_from_db()
        self.assertNotEqual(stable_id_before, self.occ.stable_id)

    def test_follows_dataset_change(self):
        """The stable identifier changes if the occurrence gets linked to another dataset (with a different dataset key)

        Note: this won't probably happen in real-world use, but it's a good practice and add extra safety
        """

        stable_id_before = self.occ.stable_id
        self.occ.source_dataset = Dataset.objects.create(
            name="New dataset", gbif_dataset_key="newdatasetid"
        )
        self.occ.save()
        self.occ.refresh_from_db()
        self.assertNotEqual(stable_id_before, self.occ.stable_id)

    def test_dont_follow_unrelated_fields(self):
        """The stable identifier should rely only on occurrence_id and dataset_key.

        This test ensures updating unrelated field doesn't change it
        """
        stable_id_before = self.occ.stable_id

        self.occ.species = Species.objects.all()[1]
        self.occ.date = datetime.date.today()
        self.occ.data_import = DataImport.objects.create(start=timezone.now())
        self.occ.source_dataset.name = "Renamed dataset"
        self.occ.source_dataset.save()
        self.occ.save()

        self.assertEqual(self.occ.stable_id, stable_id_before)
