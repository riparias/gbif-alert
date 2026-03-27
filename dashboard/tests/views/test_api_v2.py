import datetime

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Area, BasisOfRecord, DataImport, Dataset, Observation, ObservationUnseen, Species

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


class ApiV2ObservationsTests(TestCase):
    """Tests for GET /api/v2/observations/.

    Covers: HTTP status, response shape, camelCase keys, pagination,
    seenByCurrentUser (anonymous/seen/unseen), and basic filter wiring.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="obs_user", password="12345", email="obs_user@example.com"
        )

        cls.species = Species.objects.create(
            name="Procambarus fallax",
            vernacular_name="marbled crayfish",
            gbif_taxon_key=8879526,
        )
        cls.other_species = Species.objects.create(
            name="Vespa velutina",
            vernacular_name="Asian hornet",
            gbif_taxon_key=1311477,
        )
        cls.dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )
        cls.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
        cls.di = DataImport.objects.create(
            start=datetime.datetime(2024, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
        )

        cls.obs = Observation.objects.create(
            gbif_id="123",
            occurrence_id="occ:123",
            species=cls.species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 3, 10),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis_of_record,
            location=Point(4.35, 50.85, srid=4326),
        )
        cls.obs_other_species = Observation.objects.create(
            gbif_id="456",
            occurrence_id="occ:456",
            species=cls.other_species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 3, 9),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis_of_record,
        )

    # --- Basic HTTP / shape ---

    def test_observations_list_status(self):
        response = self.client.get(reverse("api-v2:observations_list"))
        self.assertEqual(response.status_code, 200)

    def test_observations_list_response_shape(self):
        """Response must have 'count' (int) and 'items' (list) at the top level."""
        response = self.client.get(reverse("api-v2:observations_list"))
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("items", data)
        self.assertIsInstance(data["count"], int)
        self.assertIsInstance(data["items"], list)

    def test_observations_list_camel_case_keys(self):
        """All expected camelCase keys must be present in each item."""
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs.pk)
        for key in ("id", "stableId", "gbifId", "lat", "lon", "scientificName",
                    "vernacularName", "datasetName", "date"):
            self.assertIn(key, item, msg=f"Missing key: {key}")

    def test_observations_list_field_values(self):
        """Field values must match the observation data."""
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs.pk)
        self.assertEqual(item["scientificName"], "Procambarus fallax")
        self.assertEqual(item["vernacularName"], "marbled crayfish")
        self.assertEqual(item["datasetName"], "Test dataset")
        self.assertEqual(item["date"], "2024-03-10")
        self.assertEqual(item["gbifId"], "123")
        # lat/lon are present (location was set)
        self.assertIsNotNone(item["lat"])
        self.assertIsNotNone(item["lon"])

    def test_observations_list_null_location(self):
        """An observation without a location must return null lat and lon."""
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs_other_species.pk)
        self.assertIsNone(item["lat"])
        self.assertIsNone(item["lon"])

    # --- seenByCurrentUser ---

    def test_seen_by_current_user_is_null_for_anonymous(self):
        """Anonymous users get null for seenByCurrentUser."""
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs.pk)
        self.assertIsNone(item["seenByCurrentUser"])

    def test_seen_by_current_user_true_when_no_unseen_record(self):
        """Observation with no ObservationUnseen entry is considered seen."""
        self.client.login(username="obs_user", password="12345")
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs.pk)
        self.assertTrue(item["seenByCurrentUser"])

    def test_seen_by_current_user_false_when_unseen_record_exists(self):
        """Observation with an ObservationUnseen entry is considered unseen."""
        ObservationUnseen.objects.create(observation=self.obs, user=self.user)
        self.client.login(username="obs_user", password="12345")
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs.pk)
        self.assertFalse(item["seenByCurrentUser"])
        ObservationUnseen.objects.filter(observation=self.obs, user=self.user).delete()

    # --- Pagination ---

    def test_pagination_count_reflects_total(self):
        """count must reflect total matching observations, not just current page."""
        response = self.client.get(reverse("api-v2:observations_list"))
        self.assertEqual(response.json()["count"], 2)

    def test_pagination_page_size_respected(self):
        """pageSize=1 must return exactly 1 item."""
        response = self.client.get(
            reverse("api-v2:observations_list"), {"pageSize": 1, "page": 1}
        )
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["count"], 2)

    def test_pagination_second_page(self):
        """Page 2 with pageSize=1 returns the second observation."""
        response_p1 = self.client.get(
            reverse("api-v2:observations_list"), {"pageSize": 1, "page": 1}
        )
        response_p2 = self.client.get(
            reverse("api-v2:observations_list"), {"pageSize": 1, "page": 2}
        )
        id_p1 = response_p1.json()["items"][0]["id"]
        id_p2 = response_p2.json()["items"][0]["id"]
        self.assertNotEqual(id_p1, id_p2)

    # --- Filter wiring ---

    def test_species_filter(self):
        """speciesIds filter must restrict results to matching observations."""
        response = self.client.get(
            reverse("api-v2:observations_list"), {"speciesIds": self.species.pk}
        )
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["id"], self.obs.pk)


class ApiV2HistogramTests(TestCase):
    """Tests for GET /api/v2/observations/histogram/."""

    @classmethod
    def setUpTestData(cls):
        cls.species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )
        cls.other_species = Species.objects.create(
            name="Vespa velutina", gbif_taxon_key=1311477
        )
        cls.dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )
        cls.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
        cls.di = DataImport.objects.create(
            start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        )
        # Two observations in different months
        cls.obs_jan = Observation.objects.create(
            gbif_id="h1",
            occurrence_id="occ:h1",
            species=cls.species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 1, 15),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis_of_record,
        )
        cls.obs_mar = Observation.objects.create(
            gbif_id="h2",
            occurrence_id="occ:h2",
            species=cls.species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 3, 10),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis_of_record,
        )
        cls.obs_other_species = Observation.objects.create(
            gbif_id="h3",
            occurrence_id="occ:h3",
            species=cls.other_species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 2, 5),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis_of_record,
        )

    def test_histogram_status(self):
        response = self.client.get(reverse("api-v2:observations_histogram"))
        self.assertEqual(response.status_code, 200)

    def test_histogram_response_is_list(self):
        response = self.client.get(reverse("api-v2:observations_histogram"))
        self.assertIsInstance(response.json(), list)

    def test_histogram_entry_shape(self):
        """Each entry must have year, month, count keys."""
        response = self.client.get(reverse("api-v2:observations_histogram"))
        for entry in response.json():
            self.assertIn("year", entry)
            self.assertIn("month", entry)
            self.assertIn("count", entry)

    def test_histogram_chronological_order(self):
        """Entries must be in ascending chronological order."""
        response = self.client.get(reverse("api-v2:observations_histogram"))
        entries = response.json()
        dates = [(e["year"], e["month"]) for e in entries]
        self.assertEqual(dates, sorted(dates))

    def test_histogram_counts_by_month(self):
        """Each month must report the correct observation count."""
        response = self.client.get(reverse("api-v2:observations_histogram"))
        by_month = {(e["year"], e["month"]): e["count"] for e in response.json()}
        self.assertEqual(by_month[(2024, 1)], 1)
        self.assertEqual(by_month[(2024, 2)], 1)
        self.assertEqual(by_month[(2024, 3)], 1)

    def test_histogram_ignores_date_filters(self):
        """startDate/endDate params must be ignored: histogram always shows full range."""
        # Passing startDate and endDate that exclude obs_jan should not affect results
        response = self.client.get(
            reverse("api-v2:observations_histogram"),
            {"startDate": "2024-02-01", "endDate": "2024-12-31"},
        )
        by_month = {(e["year"], e["month"]): e["count"] for e in response.json()}
        self.assertIn((2024, 1), by_month)
        self.assertEqual(by_month[(2024, 1)], 1)

    def test_histogram_species_filter(self):
        """speciesIds filter must restrict which observations are counted."""
        response = self.client.get(
            reverse("api-v2:observations_histogram"),
            {"speciesIds": self.species.pk},
        )
        by_month = {(e["year"], e["month"]): e["count"] for e in response.json()}
        # February only has obs_other_species, so it should be absent or 0
        self.assertNotIn((2024, 2), by_month)
