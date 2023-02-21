import datetime

from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.models import Observation, Species, DataImport, Dataset

SAMPLE_DATASET_KEY = "940821c0-3269-11df-855a-b8a03c50a862"
SAMPLE_OCCURRENCE_ID = "BR:IFBL: 00494798"
EXPECTED_STABLE_ID = "e58dabf7bcc72dc6b3e057859ed89a453eea527d"


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class StableIdentifiersTests(TestCase):
    def setUp(self):
        # Not possible to replace this by setUpTestData because some methods alter the observation => this code should
        # therefore be run before each method.
        self.species_p_fallax = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526, group="CR"
        )

        di = DataImport.objects.create(start=timezone.now())
        self.obs = Observation.objects.create(
            gbif_id=1,
            occurrence_id=SAMPLE_OCCURRENCE_ID,
            species=self.species_p_fallax,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY
            ),
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

    def test_stable_correct_value(self):
        """The stable identifier has the expected value and is therefore predictable over time"""
        self.assertEqual(self.obs.stable_id, EXPECTED_STABLE_ID)

    def test_follows_occurrence_id(self):
        """The stable identifier changes if the occurrence_id is updated"""
        stable_id_before = self.obs.stable_id
        self.obs.occurrence_id = "something new"
        self.obs.save()

        self.obs.refresh_from_db()  # Refresh is probably not necessary here, providing it for consistency with
        # test_follows_dataset_key()
        self.assertNotEqual(stable_id_before, self.obs.stable_id)

    def test_follows_dataset_key(self):
        """The stable identifier changes if the dataset key is updated

        Note: this won't probably happen in real-world use, but it's a good practice and add extra safety
        """
        stable_id_before = self.obs.stable_id
        self.obs.source_dataset.gbif_dataset_key = "something new"
        self.obs.source_dataset.save()

        self.obs.refresh_from_db()
        self.assertNotEqual(stable_id_before, self.obs.stable_id)

    def test_follows_dataset_change(self):
        """The stable identifier changes if the observation gets linked to another dataset (with a different dataset key)

        Note: this won't probably happen in real-world use, but it's a good practice and add extra safety
        """

        stable_id_before = self.obs.stable_id
        self.obs.source_dataset = Dataset.objects.create(
            name="New dataset", gbif_dataset_key="newdatasetid"
        )
        self.obs.save()
        self.obs.refresh_from_db()
        self.assertNotEqual(stable_id_before, self.obs.stable_id)

    def test_dont_follow_unrelated_fields(self):
        """The stable identifier should rely only on occurrence_id and dataset_key.

        This test ensures updating unrelated field doesn't change it
        """
        stable_id_before = self.obs.stable_id

        self.obs.species = self.species_p_fallax
        self.obs.date = datetime.date.today()
        self.obs.data_import = DataImport.objects.create(start=timezone.now())
        self.obs.source_dataset.name = "Renamed dataset"
        self.obs.source_dataset.save()
        self.obs.save()

        self.assertEqual(self.obs.stable_id, stable_id_before)
