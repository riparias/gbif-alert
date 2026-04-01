import datetime
import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Alert, Area, BasisOfRecord, DataImport, Dataset, Observation, ObservationComment, ObservationUnseen, Species

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
                    "vernacularName", "datasetName", "date",
                    "municipality", "verified", "identificationVerificationStatus", "basisOfRecord"):
            self.assertIn(key, item, msg=f"Missing key: {key}")

    def test_observations_list_new_fields(self):
        """municipality, verified, and identificationVerificationStatus must be present with correct values."""
        response = self.client.get(reverse("api-v2:observations_list"))
        item = next(i for i in response.json()["items"] if i["id"] == self.obs.pk)
        self.assertEqual(item["municipality"], "")
        self.assertIs(item["verified"], False)
        self.assertEqual(item["identificationVerificationStatus"], "")
        self.assertEqual(item["basisOfRecord"], "HUMAN_OBSERVATION")

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


class ApiV2ObservationsSortingTests(TestCase):
    """Tests for the orderBy / orderDir parameters of GET /api/v2/observations/.

    Fixture contains two observations designed so each sort column produces a
    distinct, deterministic order:

    - obs_alpha: species "Anas platyrhynchos" / dataset "Alpha dataset" / date 2024-01-01
    - obs_zeta:  species "Zeta vulgaris"      / dataset "Zeta dataset"  / date 2024-06-15

    Expected orders per sort key:
      date asc:               obs_alpha, obs_zeta
      date desc (default):    obs_zeta,  obs_alpha
      scientificName asc:     obs_alpha, obs_zeta
      scientificName desc:    obs_zeta,  obs_alpha
      datasetName asc:        obs_alpha, obs_zeta
      datasetName desc:       obs_zeta,  obs_alpha
    """

    @classmethod
    def setUpTestData(cls):
        cls.species_alpha = Species.objects.create(
            name="Anas platyrhynchos", gbif_taxon_key=2498252
        )
        cls.species_zeta = Species.objects.create(
            name="Zeta vulgaris", gbif_taxon_key=9999999
        )
        cls.dataset_alpha = Dataset.objects.create(
            name="Alpha dataset",
            gbif_dataset_key="aaaaaaaa-0000-0000-0000-000000000001",
        )
        cls.dataset_zeta = Dataset.objects.create(
            name="Zeta dataset",
            gbif_dataset_key="zzzzzzzz-0000-0000-0000-000000000002",
        )
        cls.basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
        cls.di = DataImport.objects.create(
            start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        )
        cls.obs_alpha = Observation.objects.create(
            gbif_id="sort1",
            occurrence_id="occ:sort1",
            species=cls.species_alpha,
            source_dataset=cls.dataset_alpha,
            date=datetime.date(2024, 1, 1),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis,
        )
        cls.obs_zeta = Observation.objects.create(
            gbif_id="sort2",
            occurrence_id="occ:sort2",
            species=cls.species_zeta,
            source_dataset=cls.dataset_zeta,
            date=datetime.date(2024, 6, 15),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis,
        )

    def _ids(self, **params):
        """Return the ordered list of observation ids from a GET request."""
        response = self.client.get(reverse("api-v2:observations_list"), params)
        self.assertEqual(response.status_code, 200)
        return [item["id"] for item in response.json()["items"]]

    # --- date ---

    def test_default_order_is_date_descending(self):
        """With no sort params the newest observation must come first."""
        ids = self._ids()
        alpha_pos = ids.index(self.obs_alpha.pk)
        zeta_pos = ids.index(self.obs_zeta.pk)
        self.assertLess(zeta_pos, alpha_pos)

    def test_order_by_date_descending_explicit(self):
        """orderBy=date&orderDir=desc puts the newest observation first."""
        ids = self._ids(orderBy="date", orderDir="desc")
        self.assertLess(ids.index(self.obs_zeta.pk), ids.index(self.obs_alpha.pk))

    def test_order_by_date_ascending(self):
        """orderBy=date&orderDir=asc puts the oldest observation first."""
        ids = self._ids(orderBy="date", orderDir="asc")
        self.assertLess(ids.index(self.obs_alpha.pk), ids.index(self.obs_zeta.pk))

    # --- scientificName ---

    def test_order_by_scientific_name_ascending(self):
        """orderBy=scientificName&orderDir=asc puts Anas before Zeta."""
        ids = self._ids(orderBy="scientificName", orderDir="asc")
        self.assertLess(ids.index(self.obs_alpha.pk), ids.index(self.obs_zeta.pk))

    def test_order_by_scientific_name_descending(self):
        """orderBy=scientificName&orderDir=desc puts Zeta before Anas."""
        ids = self._ids(orderBy="scientificName", orderDir="desc")
        self.assertLess(ids.index(self.obs_zeta.pk), ids.index(self.obs_alpha.pk))

    # --- datasetName ---

    def test_order_by_dataset_name_ascending(self):
        """orderBy=datasetName&orderDir=asc puts Alpha dataset before Zeta dataset."""
        ids = self._ids(orderBy="datasetName", orderDir="asc")
        self.assertLess(ids.index(self.obs_alpha.pk), ids.index(self.obs_zeta.pk))

    def test_order_by_dataset_name_descending(self):
        """orderBy=datasetName&orderDir=desc puts Zeta dataset before Alpha dataset."""
        ids = self._ids(orderBy="datasetName", orderDir="desc")
        self.assertLess(ids.index(self.obs_zeta.pk), ids.index(self.obs_alpha.pk))

    # --- robustness ---

    def test_unknown_order_by_falls_back_to_date(self):
        """An unrecognised orderBy value must not crash - falls back to date sort."""
        response = self.client.get(
            reverse("api-v2:observations_list"), {"orderBy": "nonExistentField"}
        )
        self.assertEqual(response.status_code, 200)
        # Default date-desc order: obs_zeta (newer) before obs_alpha (older)
        ids = [item["id"] for item in response.json()["items"]]
        self.assertLess(ids.index(self.obs_zeta.pk), ids.index(self.obs_alpha.pk))

    def test_unknown_order_dir_treated_as_desc(self):
        """Any orderDir value other than 'asc' must be treated as descending."""
        ids = self._ids(orderBy="date", orderDir="INVALID")
        self.assertLess(ids.index(self.obs_zeta.pk), ids.index(self.obs_alpha.pk))


class ApiV2ObservationDetailTests(TestCase):
    """Tests for GET /api/v2/observations/{stable_id}/.

    Covers: 404, response shape, canBeMarkedUnseen logic, and comments.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="detail_user", password="12345", email="detail_user@example.com"
        )
        cls.commenter = User.objects.create_user(
            username="commenter", password="12345", email="commenter@example.com"
        )

        cls.species = Species.objects.create(
            name="Harmonia axyridis",
            vernacular_name="harlequin ladybird",
            gbif_taxon_key=1234567,
        )
        cls.dataset = Dataset.objects.create(
            name="Detail dataset",
            gbif_dataset_key="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        cls.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
        cls.di = DataImport.objects.create(
            start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        )
        cls.obs = Observation.objects.create(
            gbif_id="999",
            occurrence_id="occ:999",
            species=cls.species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 5, 1),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis_of_record,
            location=Point(4.35, 50.85, srid=4326),
        )

    def _url(self):
        return f"/api/v2/observations/{self.obs.stable_id}/"

    # --- Basic HTTP / shape ---

    def test_detail_404_for_unknown_stable_id(self):
        response = self.client.get("/api/v2/observations/nonexistent/")
        self.assertEqual(response.status_code, 404)

    def test_detail_status_200(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_detail_camel_case_keys(self):
        """All expected camelCase keys must be present in the response."""
        response = self.client.get(self._url())
        data = response.json()
        for key in (
            "id", "stableId", "gbifId", "lat", "lon",
            "scientificName", "vernacularName", "datasetName", "datasetGbifKey",
            "date", "basisOfRecord", "seenByCurrentUser", "canBeMarkedUnseen",
            "comments",
        ):
            self.assertIn(key, data, msg=f"Missing key: {key}")

    def test_detail_field_values(self):
        response = self.client.get(self._url())
        data = response.json()
        self.assertEqual(data["stableId"], self.obs.stable_id)
        self.assertEqual(data["scientificName"], "Harmonia axyridis")
        self.assertEqual(data["vernacularName"], "harlequin ladybird")
        self.assertEqual(data["datasetName"], "Detail dataset")
        self.assertEqual(data["date"], "2024-05-01")

    # --- canBeMarkedUnseen ---

    def test_can_be_marked_unseen_false_for_anonymous(self):
        response = self.client.get(self._url())
        self.assertFalse(response.json()["canBeMarkedUnseen"])

    def test_can_be_marked_unseen_false_when_no_matching_alert(self):
        """Authenticated user with no alerts: cannot mark unseen."""
        self.client.force_login(self.user)
        response = self.client.get(self._url())
        self.assertFalse(response.json()["canBeMarkedUnseen"])

    def test_can_be_marked_unseen_true_when_alert_matches(self):
        """Authenticated user with a matching alert: can mark unseen."""
        self.client.force_login(self.user)
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        alert.species.add(self.obs.species)
        response = self.client.get(self._url())
        self.assertTrue(response.json()["canBeMarkedUnseen"])

    # --- comments ---

    def test_comments_returned_with_author_username(self):
        """Comments list must include the author's username."""
        ObservationComment.objects.create(
            observation=self.obs, author=self.commenter, text="Nice find!"
        )
        response = self.client.get(self._url())
        comments = response.json()["comments"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["authorUsername"], "commenter")
        self.assertEqual(comments[0]["text"], "Nice find!")

    def test_comments_empty_list_when_none(self):
        response = self.client.get(self._url())
        self.assertEqual(response.json()["comments"], [])


class ApiV2ObservationsMunicipalityVerifiedSortTests(TestCase):
    """Tests for sorting by municipality and verified in GET /api/v2/observations/.

    Fixture:
    - obs_gent: municipality="Gent",  verified=True
    - obs_mons: municipality="Mons",  verified=False

    Expected orders:
      municipality asc:  obs_gent, obs_mons  (G before M)
      municipality desc: obs_mons, obs_gent
      verified asc:      obs_mons (False=0), obs_gent (True=1)
      verified desc:     obs_gent (True=1),  obs_mons (False=0)
    """

    @classmethod
    def setUpTestData(cls):
        cls.species = Species.objects.create(
            name="Testus sorticus", gbif_taxon_key=9990001
        )
        cls.dataset = Dataset.objects.create(
            name="Sort test dataset",
            gbif_dataset_key="11111111-0000-0000-0000-000000000099",
        )
        cls.basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
        cls.di = DataImport.objects.create(
            start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        )
        cls.obs_gent = Observation.objects.create(
            gbif_id="munis1",
            occurrence_id="occ:munis1",
            species=cls.species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 1, 1),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis,
            municipality="Gent",
            verified=True,
        )
        cls.obs_mons = Observation.objects.create(
            gbif_id="munis2",
            occurrence_id="occ:munis2",
            species=cls.species,
            source_dataset=cls.dataset,
            date=datetime.date(2024, 1, 2),
            data_import=cls.di,
            initial_data_import=cls.di,
            basis_of_record=cls.basis,
            municipality="Mons",
            verified=False,
        )

    def _ids(self, **params):
        """Return the ordered list of observation ids from a GET request."""
        response = self.client.get(reverse("api-v2:observations_list"), params)
        self.assertEqual(response.status_code, 200)
        return [item["id"] for item in response.json()["items"]]

    def test_order_by_municipality_ascending(self):
        """orderBy=municipality&orderDir=asc puts Gent before Mons."""
        ids = self._ids(orderBy="municipality", orderDir="asc")
        self.assertLess(ids.index(self.obs_gent.pk), ids.index(self.obs_mons.pk))

    def test_order_by_municipality_descending(self):
        """orderBy=municipality&orderDir=desc puts Mons before Gent."""
        ids = self._ids(orderBy="municipality", orderDir="desc")
        self.assertLess(ids.index(self.obs_mons.pk), ids.index(self.obs_gent.pk))

    def test_order_by_verified_ascending(self):
        """orderBy=verified&orderDir=asc puts False (obs_mons) before True (obs_gent)."""
        ids = self._ids(orderBy="verified", orderDir="asc")
        self.assertLess(ids.index(self.obs_mons.pk), ids.index(self.obs_gent.pk))

    def test_order_by_verified_descending(self):
        """orderBy=verified&orderDir=desc puts True (obs_gent) before False (obs_mons)."""
        ids = self._ids(orderBy="verified", orderDir="desc")
        self.assertLess(ids.index(self.obs_gent.pk), ids.index(self.obs_mons.pk))


class ApiV2AlertTests(TestCase):
    """Tests for the /api/v2/alerts/ CRUD endpoints."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="alertuser", password="12345", email="alert@example.com"
        )
        cls.other_user = User.objects.create_user(
            username="otheruser", password="12345", email="other@example.com"
        )
        cls.sp1 = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
        cls.sp2 = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
        cls.alert = Alert.objects.create(
            name="My alert #1", user=cls.user, email_notifications_frequency="N"
        )
        cls.alert.species.add(cls.sp1)

    # --- /api/v2/alerts/ (list) ---

    def test_alerts_list_requires_auth(self):
        response = self.client.get("/api/v2/alerts/")
        self.assertEqual(response.status_code, 401)

    def test_alerts_list_returns_own_alerts(self):
        self.client.login(username="alertuser", password="12345")
        response = self.client.get("/api/v2/alerts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "My alert #1")
        self.assertIn("speciesIds", data[0])
        self.assertIn("unseenCount", data[0])

    def test_alerts_list_does_not_include_other_users_alerts(self):
        other_alert = Alert.objects.create(
            name="Other alert", user=self.other_user, email_notifications_frequency="N"
        )
        other_alert.species.add(self.sp1)
        self.client.login(username="alertuser", password="12345")
        response = self.client.get("/api/v2/alerts/")
        self.assertEqual(len(response.json()), 1)

    # --- POST /api/v2/alerts/ (create) ---

    def test_alert_create_success(self):
        self.client.login(username="alertuser", password="12345")
        payload = json.dumps({"name": "New alert", "speciesIds": [self.sp1.pk]})
        response = self.client.post("/api/v2/alerts/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Alert.objects.filter(name="New alert", user=self.user).exists())

    def test_alert_create_no_species_returns_422(self):
        self.client.login(username="alertuser", password="12345")
        payload = json.dumps({"name": "Bad alert", "speciesIds": []})
        response = self.client.post("/api/v2/alerts/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 422)
        self.assertIn("species", response.json()["errors"])

    def test_alert_create_requires_auth(self):
        payload = json.dumps({"name": "Unauth alert", "speciesIds": [self.sp1.pk]})
        response = self.client.post("/api/v2/alerts/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    # --- GET /api/v2/alerts/{alert_id}/ (detail) ---

    def test_alert_detail_returns_correct_fields(self):
        self.client.login(username="alertuser", password="12345")
        response = self.client.get(f"/api/v2/alerts/{self.alert.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "My alert #1")
        self.assertEqual(data["speciesIds"], [self.sp1.pk])
        self.assertIn("speciesList", data)
        self.assertIn("emailNotificationsFrequencyDisplay", data)

    def test_alert_detail_wrong_user_returns_404(self):
        self.client.login(username="otheruser", password="12345")
        response = self.client.get(f"/api/v2/alerts/{self.alert.pk}/")
        self.assertEqual(response.status_code, 404)

    # --- PUT /api/v2/alerts/{alert_id}/ (update) ---

    def test_alert_update_success(self):
        self.client.login(username="alertuser", password="12345")
        payload = json.dumps({"name": "Renamed alert", "speciesIds": [self.sp1.pk, self.sp2.pk]})
        response = self.client.put(
            f"/api/v2/alerts/{self.alert.pk}/", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.name, "Renamed alert")
        self.assertEqual(self.alert.species.count(), 2)

    def test_alert_update_wrong_user_returns_404(self):
        self.client.login(username="otheruser", password="12345")
        payload = json.dumps({"name": "Hacked", "speciesIds": [self.sp1.pk]})
        response = self.client.put(
            f"/api/v2/alerts/{self.alert.pk}/", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    # --- DELETE /api/v2/alerts/{alert_id}/ ---

    def test_alert_delete_success(self):
        to_delete = Alert.objects.create(
            name="To delete", user=self.user, email_notifications_frequency="N"
        )
        to_delete.species.add(self.sp1)
        self.client.login(username="alertuser", password="12345")
        response = self.client.delete(f"/api/v2/alerts/{to_delete.pk}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Alert.objects.filter(pk=to_delete.pk).exists())

    def test_alert_delete_wrong_user_returns_404(self):
        self.client.login(username="otheruser", password="12345")
        response = self.client.delete(f"/api/v2/alerts/{self.alert.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Alert.objects.filter(pk=self.alert.pk).exists())

    # --- GET /api/v2/alerts/{alert_id}/as-filters/ ---

    def test_alert_as_filters_returns_dashboard_filter_shape(self):
        self.client.login(username="alertuser", password="12345")
        response = self.client.get(f"/api/v2/alerts/{self.alert.pk}/as-filters/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["speciesIds"], [self.sp1.pk])
        self.assertEqual(data["status"], "unseen")
        self.assertIn("verifiedFilter", data)
        self.assertIn("areaFilterMode", data)

    # --- GET /api/v2/alerts/suggest-name/ ---

    def test_suggest_name_returns_first_available(self):
        # "My alert #1" is taken; next should be "My alert #2"
        self.client.login(username="alertuser", password="12345")
        response = self.client.get("/api/v2/alerts/suggest-name/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "My alert #2")

    # --- GET /api/v2/alerts/notification-frequencies/ ---

    def test_notification_frequencies_list(self):
        response = self.client.get("/api/v2/alerts/notification-frequencies/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [f["id"] for f in data]
        self.assertIn("N", ids)
        self.assertIn("D", ids)
        self.assertIn("W", ids)
        self.assertIn("M", ids)
