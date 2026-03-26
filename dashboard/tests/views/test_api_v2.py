import datetime

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Area, BasisOfRecord, DataImport, Dataset, Species

# A minimal polygon - geometry is irrelevant for these tests.
SIMPLE_POLYGON = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)), srid=4326))


class ApiV2FilterListsTests(TestCase):
    """Tests for the /api/v2/ list endpoints that populate filter dropdowns.

    These tests focus on:
    - HTTP status and response shape (correct camelCase keys)
    - Resolver correctness (field renames, computed values)
    - Edge cases: empty tags, no data
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.area_owner = User.objects.create_user(
            username="area_owner", password="12345", email="area_owner@example.com"
        )
        cls.other_user = User.objects.create_user(
            username="other_user", password="12345", email="other_user@example.com"
        )

        cls.species = Species.objects.create(
            name="Procambarus fallax",
            vernacular_name="marbled crayfish",
            gbif_taxon_key=8879526,
        )
        cls.species_no_tags = Species.objects.create(
            name="Orconectes virilis",
            vernacular_name="",
            gbif_taxon_key=2227064,
        )
        cls.species.tags.add("invasive", "crustacean")

        cls.dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )

        cls.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")

        cls.di = DataImport.objects.create(
            start=datetime.datetime(2024, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2024, 3, 15, 11, 0, 0, tzinfo=datetime.timezone.utc),
            completed=True,
        )

        cls.public_area = Area.objects.create(
            name="Public area", mpoly=SIMPLE_POLYGON
        )
        cls.user_area = Area.objects.create(
            name="User area", owner=cls.area_owner, mpoly=SIMPLE_POLYGON
        )

    # --- /api/v2/species/ ---

    def test_species_list_status(self):
        response = self.client.get(reverse("api-v2:species_list"))
        self.assertEqual(response.status_code, 200)

    def test_species_list_camel_case_keys(self):
        """Field renames must produce camelCase JSON keys."""
        response = self.client.get(reverse("api-v2:species_list"))
        species_data = [s for s in response.json() if s["id"] == self.species.pk]
        self.assertEqual(len(species_data), 1)
        entry = species_data[0]

        self.assertEqual(entry["id"], self.species.pk)
        self.assertEqual(entry["scientificName"], "Procambarus fallax")
        self.assertEqual(entry["vernacularName"], "marbled crayfish")
        self.assertEqual(entry["gbifTaxonKey"], 8879526)
        self.assertCountEqual(entry["tags"], ["invasive", "crustacean"])

    def test_species_list_empty_tags(self):
        """A species with no tags returns an empty list, not null."""
        response = self.client.get(reverse("api-v2:species_list"))
        entry = next(s for s in response.json() if s["id"] == self.species_no_tags.pk)
        self.assertEqual(entry["tags"], [])

    # --- /api/v2/datasets/ ---

    def test_datasets_list_status(self):
        response = self.client.get(reverse("api-v2:datasets_list"))
        self.assertEqual(response.status_code, 200)

    def test_datasets_list_gbif_key_resolver(self):
        """gbifKey must be taken from Dataset.gbif_dataset_key, not a non-existent field."""
        response = self.client.get(reverse("api-v2:datasets_list"))
        entry = next(d for d in response.json() if d["id"] == self.dataset.pk)

        self.assertEqual(entry["gbifKey"], "4fa7b334-ce0d-4e88-aaae-2e0c138d049e")
        self.assertEqual(entry["name"], "Test dataset")

    # --- /api/v2/areas/ ---

    def test_areas_list_anonymous_sees_only_public(self):
        response = self.client.get(reverse("api-v2:areas_list"))
        self.assertEqual(response.status_code, 200)
        ids = [a["id"] for a in response.json()]
        self.assertIn(self.public_area.pk, ids)
        self.assertNotIn(self.user_area.pk, ids)

    def test_areas_list_owner_sees_own_and_public(self):
        self.client.login(username="area_owner", password="12345")
        response = self.client.get(reverse("api-v2:areas_list"))
        ids = [a["id"] for a in response.json()]
        self.assertIn(self.public_area.pk, ids)
        self.assertIn(self.user_area.pk, ids)

    def test_areas_list_other_user_sees_only_public(self):
        self.client.login(username="other_user", password="12345")
        response = self.client.get(reverse("api-v2:areas_list"))
        ids = [a["id"] for a in response.json()]
        self.assertIn(self.public_area.pk, ids)
        self.assertNotIn(self.user_area.pk, ids)

    def test_areas_list_is_user_specific_field(self):
        """isUserSpecific must reflect area ownership correctly."""
        self.client.login(username="area_owner", password="12345")
        response = self.client.get(reverse("api-v2:areas_list"))
        by_id = {a["id"]: a for a in response.json()}
        self.assertFalse(by_id[self.public_area.pk]["isUserSpecific"])
        self.assertTrue(by_id[self.user_area.pk]["isUserSpecific"])

    # --- /api/v2/basis-of-record/ ---

    def test_basis_of_record_list_status(self):
        response = self.client.get(reverse("api-v2:basis_of_record_list"))
        self.assertEqual(response.status_code, 200)

    def test_basis_of_record_list_fields(self):
        response = self.client.get(reverse("api-v2:basis_of_record_list"))
        entry = next(b for b in response.json() if b["id"] == self.basis_of_record.pk)
        self.assertEqual(entry["name"], "HUMAN_OBSERVATION")

    # --- /api/v2/data-imports/ ---

    def test_data_imports_list_status(self):
        response = self.client.get(reverse("api-v2:data_imports_list"))
        self.assertEqual(response.status_code, 200)

    def test_data_imports_list_computed_name(self):
        """name is computed as 'Data import #N', not a model field."""
        response = self.client.get(reverse("api-v2:data_imports_list"))
        entry = next(d for d in response.json() if d["id"] == self.di.pk)
        self.assertEqual(entry["name"], f"Data import #{self.di.pk}")

    def test_data_imports_list_start_timestamp(self):
        """startTimestamp is present and formatted as an ISO datetime string."""
        response = self.client.get(reverse("api-v2:data_imports_list"))
        entry = next(d for d in response.json() if d["id"] == self.di.pk)
        self.assertEqual(entry["startTimestamp"], "2024-03-15T10:00:00Z")
