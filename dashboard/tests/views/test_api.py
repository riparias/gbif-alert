import datetime

from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import Occurrence, Species, DataImport, Dataset


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.first_species = Species.objects.all()[0]
        cls.second_species = Species.objects.all()[1]

        cls.di = DataImport.objects.create(start=timezone.now())
        cls.dataset = Dataset.objects.create(
            name="Test dataset", gbif_id="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )

        Occurrence.objects.create(
            gbif_id=1,
            species=cls.first_species,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=cls.di,
            source_dataset=cls.dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )
        Occurrence.objects.create(
            gbif_id=2,
            species=cls.second_species,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=cls.di,
            source_dataset=cls.dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )
        Occurrence.objects.create(
            gbif_id=3,
            species=cls.second_species,
            date=datetime.date.today(),
            data_import=cls.di,
            source_dataset=cls.dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )

    def test_occurrences_json_no_location(self):
        """Regression test: no error 500 in occurrences_json if we have locations without a location"""
        Occurrence.objects.create(
            gbif_id=4,
            species=ApiTests.second_species,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.dataset,
            location=None,
        )
        base_url = reverse("dashboard:api-occurrences-json")
        response = self.client.get(f"{base_url}?limit=10&page_number=1")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 4)

    def test_occurrences_json_basic_no_filters(self):
        """Basic tests for the endpoint, no filters used"""
        base_url = reverse("dashboard:api-occurrences-json")
        response = self.client.get(f"{base_url}?limit=10&page_number=1")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # All 3 occurrences should be on this first page, in undefined order
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(json_data["totalResultsCount"], len(json_data["results"]))
        self.assertEqual(json_data["pageNumber"], 1)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 1)
        found = False
        for r in json_data["results"]:
            if r["speciesName"] == "Elodea nuttallii":
                found = True
        self.assertTrue(found)

    def test_occurrences_json_ordering(self):
        base_url = reverse("dashboard:api-occurrences-json")
        response = self.client.get(f"{base_url}?limit=10&page_number=1&order=-pk")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # Check that it's sorted by reverse primary key
        self.assertEqual(json_data["results"][0]["id"], 3)
        self.assertEqual(json_data["results"][1]["id"], 2)
        self.assertEqual(json_data["results"][2]["id"], 1)

    def test_occurrences_json_pagination_base(self):
        base_url = reverse("dashboard:api-occurrences-json")

        response = self.client.get(f"{base_url}?limit=2&page_number=1")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(len(json_data["results"]), 2)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 2)
        self.assertEqual(json_data["pageNumber"], 1)

        response = self.client.get(f"{base_url}?limit=2&page_number=2")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(len(json_data["results"]), 1)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 2)
        self.assertEqual(json_data["pageNumber"], 2)

    def test_occurrences_json_pagination_greater_than_max(self):
        """If the requested page number is greater than the number of pages, it returns the last page"""
        base_url = reverse("dashboard:api-occurrences-json")
        response = self.client.get(f"{base_url}?limit=2&page_number=3")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(len(json_data["results"]), 1)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 2)
        self.assertEqual(json_data["pageNumber"], 2)

    def test_occurrences_json_pagination_negative(self):
        """If the requested page number is negative, it returns the last page"""
        base_url = reverse("dashboard:api-occurrences-json")
        response = self.client.get(f"{base_url}?limit=2&page_number=-5")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(len(json_data["results"]), 1)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 2)
        self.assertEqual(json_data["pageNumber"], 2)

    def test_occurrences_json_min_date_filter(self):
        base_url = reverse("dashboard:api-occurrences-json")
        response = self.client.get(
            f"{base_url}?limit=10&page_number=1&startDate={datetime.date.today().strftime('%Y-%m-%d')}"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)
        self.assertEqual(json_data["results"][0]["gbifId"], "3")

    def test_occurrences_json_max_date_filter(self):
        base_url = reverse("dashboard:api-occurrences-json")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        response = self.client.get(
            f"{base_url}?limit=10&page_number=1&endDate={yesterday.strftime('%Y-%m-%d')}"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 2)
        self.assertIn(json_data["results"][0]["gbifId"], ["1", "2"])
        self.assertIn(json_data["results"][1]["gbifId"], ["1", "2"])

    def test_occurrences_json_species_filter(self):
        base_url = reverse("dashboard:api-occurrences-json")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 2)
        self.assertIn(json_data["results"][0]["gbifId"], ["2", "3"])
        self.assertIn(json_data["results"][1]["gbifId"], ["2", "3"])

    def test_occurrences_json_multiple_species_filter_case1(self):
        """occurrences_json accept to filter per multiple species

        Case 1: Explicitly requests all species. Results should be the same than no filter"""
        base_url = reverse("dashboard:api-occurrences-json")

        json_data_all_species = self.client.get(
            f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&speciesIds[]={ApiTests.first_species.pk}"
        ).json()
        json_data_no_species_filters = self.client.get(
            f"{base_url}?limit=10&page_number=1"
        ).json()
        self.assertEqual(json_data_all_species, json_data_no_species_filters)

    def test_occurrences_json_multiple_species_filter_case2(self):
        """occurrences_json accept to filter per multiple species

        Case 2: request occurrences for species 1 and 3
        """
        # We need one more species and one related occurrence to perform this test
        species_tetraodon = Species.objects.create(
            name="Tetraodon fluviatilis",
            gbif_taxon_key=5213564,
            group="PL",
            category="E",
        )
        Occurrence.objects.create(
            gbif_id=1000,
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.dataset,
        )

        base_url = reverse("dashboard:api-occurrences-json")

        json_data = self.client.get(
            f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.first_species.pk}&speciesIds[]={species_tetraodon.pk}"
        ).json()

        self.assertEqual(json_data["totalResultsCount"], 2)
        for result in json_data["results"]:
            self.assertIn(
                result["speciesName"],
                [ApiTests.first_species.name, species_tetraodon.name],
            )

    def test_occurrences_json_combined_filters(self):
        base_url = reverse("dashboard:api-occurrences-json")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&endDate={yesterday.strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)
        self.assertEqual(json_data["results"][0]["gbifId"], "2")

    def test_occurrences_json_no_results(self):
        base_url = reverse("dashboard:api-occurrences-json")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.first_species.pk}&startDate={datetime.date.today().strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 0)
        self.assertEqual(json_data["results"], [])

    def test_occurrences_counter_no_filters(self):
        response = self.client.get(reverse("dashboard:api-occurrences-counter"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 3)

    def test_occurrences_counter_species_filters(self):
        base_url = reverse("dashboard:api-occurrences-counter")
        url_with_params = f"{base_url}?speciesIds[]={ApiTests.second_species.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 2)

    def test_occurrence_counter_multiple_species_filter_case1(self):
        """We explicitly request all species: result should be identical to no species filtering"""
        base_url = reverse("dashboard:api-occurrences-counter")
        json_data_explicit = self.client.get(
            f"{base_url}?speciesIds[]={ApiTests.second_species.pk}&speciesIds[]={ApiTests.first_species.pk}"
        ).json()
        json_data_nofilters = self.client.get(f"{base_url}").json()
        self.assertEqual(json_data_explicit, json_data_nofilters)

    def test_occurrence_counter_multiple_species_filter_case2(self):
        """We add a third species and check we can ask a count for species 2 and 3 only"""
        # We need one more species and related occurrences to perform this test
        species_tetraodon = Species.objects.create(
            name="Tetraodon fluviatilis",
            gbif_taxon_key=5213564,
            group="PL",
            category="E",
        )
        Occurrence.objects.create(
            gbif_id=1000,
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.dataset,
        )
        Occurrence.objects.create(
            gbif_id=1001,
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.dataset,
        )
        Occurrence.objects.create(
            gbif_id=1002,
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.dataset,
        )

        base_url = reverse("dashboard:api-occurrences-counter")
        json_data = self.client.get(
            f"{base_url}?speciesIds[]={ApiTests.second_species.pk}&speciesIds[]={species_tetraodon.pk}"
        ).json()
        self.assertEqual(json_data["count"], 5)

    def test_occurrences_counter_min_date_filter(self):
        base_url = reverse("dashboard:api-occurrences-counter")
        url_with_params = (
            f"{base_url}?startDate={datetime.date.today().strftime('%Y-%m-%d')}"
        )
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 1)

    def test_occurrences_counter_max_date_filter(self):
        base_url = reverse("dashboard:api-occurrences-counter")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        url_with_params = f"{base_url}?endDate={yesterday.strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 2)

    def test_occurences_counter_combined_filters(self):
        """Counter is correct when filtering by species and end date"""
        base_url = reverse("dashboard:api-occurrences-counter")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        url_with_params = f"{base_url}?endDate={yesterday.strftime('%Y-%m-%d')}&speciesIds[]={ApiTests.second_species.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 1)

    def test_species_list_json(self):
        response = self.client.get(reverse("dashboard:api-species-list-json"))
        self.assertEqual(response.status_code, 200)
        # There's already 18 entries in the species table thanks to a data migration (0002_populate_initial_species.py)

        json_data = response.json()
        self.assertEqual(len(json_data), 18)

        # Check the main fields are there (no KeyError exception)
        json_data[0]["scientificName"]
        json_data[0]["id"]
        json_data[0]["gbifTaxonKey"]

        # Check a specific one can be found
        found = False
        for entry in json_data:
            if entry["scientificName"] == "Elodea nuttallii":
                found = True
                break

        self.assertTrue(found)
