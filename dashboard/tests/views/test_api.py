import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.utils import timezone

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    Area,
    ObservationView,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()
OCTOBER_8_2021 = datetime.datetime.strptime("2021-10-08", "%Y-%m-%d").date()


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.first_species = Species.objects.all()[0]
        cls.second_species = Species.objects.all()[1]
        cls.di = DataImport.objects.create(start=timezone.now())
        cls.first_dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )
        cls.second_dataset = Dataset.objects.create(
            name="Test dataset #2",
            gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
        )

        Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=cls.first_species,
            date=SEPTEMBER_13_2021,
            data_import=cls.di,
            source_dataset=cls.first_dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )
        second_occ = Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=cls.second_species,
            date=SEPTEMBER_13_2021,
            data_import=cls.di,
            source_dataset=cls.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=cls.second_species,
            date=OCTOBER_8_2021,
            data_import=cls.di,
            source_dataset=cls.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )

        cls.global_area_andenne = Area.objects.create(
            name="Global polygon - Andenne",
            # Covers Namur-Liège area (includes Andenne but not Lillois)
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (4.7866, 50.5200),
                        (5.6271, 50.6839),
                        (5.6930, 50.5724),
                        (4.8306, 50.4116),
                        (4.7866, 50.5200),
                    ),
                    srid=4326,
                ),
                srid=4326,
            ),
        )

        cls.global_area_lillois = Area.objects.create(
            name="Global polygon - Lillois",
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (4.3164, 50.6658),
                        (4.4025, 50.6658),
                        (4.4025, 50.6164),
                        (4.3164, 50.6164),
                        (4.3164, 50.6658),
                    ),
                    srid=4326,
                ),
                srid=4326,
            ),
        )

        User = get_user_model()
        cls.area_owner = User.objects.create_user(
            username="frusciante",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        cls.another_user = User.objects.create_user(
            username="frusciante1",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante1@gmail.com",
        )

        cls.user_area = Area.objects.create(
            name="User polygon",
            owner=cls.area_owner,
            mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
        )

        ObservationView.objects.create(occurrence=second_occ, user=cls.another_user)

    def test_areas_list_json_anonymous(self):
        """Getting the list of areas as an anonymous user"""
        response = self.client.get(reverse("dashboard:api-areas-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Make sure we only get the global ones
        self.assertEqual(len(json_data), 2)

        for the_area in json_data:
            self.assertTrue(the_area["name"].startswith("Global polygon"))
            self.assertFalse(the_area["isUserSpecific"])

    def test_areas_list_json_owner(self):
        """Getting the list of areas as an authenticated user that has a personal area"""
        self.client.login(username="frusciante", password="12345")
        response = self.client.get(reverse("dashboard:api-areas-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Make sure we get global one, but also the user-specific one
        self.assertEqual(len(json_data), 3)
        for area in json_data:
            self.assertIn(
                area["name"],
                (
                    "Global polygon - Andenne",
                    "Global polygon - Lillois",
                    "User polygon",
                ),
            )

    def test_areas_list_json_otheruser(self):
        """Getting the list of areas as an authenticated user that as NO personal area

        (result should be identical to test_areas_list_json_anonymous())
        """
        self.client.login(username="frusciante1", password="12345")
        response = self.client.get(reverse("dashboard:api-areas-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Make sure we only get the global ones
        self.assertEqual(len(json_data), 2)

        for the_area in json_data:
            self.assertTrue(the_area["name"].startswith("Global polygon - "))
            self.assertFalse(the_area["isUserSpecific"])

    def test_area_geojson_anonymous(self):
        """Anonymous users can get the global areas, not the user-specific ones"""

        # Case 1: we request a global area
        response = self.client.get(
            reverse(
                "dashboard:api-area-geojson",
                kwargs={"id": ApiTests.global_area_andenne.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/json")
        # Make sure it looks like GeoJSON
        json_data = response.json()
        self.assertEqual(json_data["type"], "FeatureCollection")
        json_data["features"]

        # Case 2: we request a user-specific one
        response = self.client.get(
            reverse("dashboard:api-area-geojson", kwargs={"id": ApiTests.user_area.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"")

    def test_area_geojson_owner(self):
        """The area owner can get the global areas, but also its own"""

        self.client.login(username="frusciante", password="12345")
        # Case 1: we request the global area
        response = self.client.get(
            reverse(
                "dashboard:api-area-geojson",
                kwargs={"id": ApiTests.global_area_andenne.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/json")
        # Make sure it looks like GeoJSON
        json_data = response.json()
        self.assertEqual(json_data["type"], "FeatureCollection")
        json_data["features"]

        # Case 2: we request a user-specific one
        response = self.client.get(
            reverse("dashboard:api-area-geojson", kwargs={"id": ApiTests.user_area.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/json")
        # Make sure it looks like GeoJSON
        json_data = response.json()
        self.assertEqual(json_data["type"], "FeatureCollection")
        json_data["features"]

    def test_area_geojson_otheruser(self):
        """A logged-in user that has no specific area: same result than anonymous"""
        self.client.login(username="frusciante1", password="12345")

        response = self.client.get(
            reverse(
                "dashboard:api-area-geojson",
                kwargs={"id": ApiTests.global_area_andenne.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/json")
        # Make sure it looks like GeoJSON
        json_data = response.json()
        self.assertEqual(json_data["type"], "FeatureCollection")
        json_data["features"]

        # Case 2: we request a user-specific one
        response = self.client.get(
            reverse("dashboard:api-area-geojson", kwargs={"id": ApiTests.user_area.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"")

    def test_observations_json_view_data(self):
        """If the user is authenticated, there is data about which occurrences were already viewed by that user"""
        self.client.login(username="frusciante1", password="12345")
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id")
        json_data = response.json()
        self.assertEqual(json_data["results"][0]["viewedByCurrentUser"], False)
        self.assertEqual(json_data["results"][1]["viewedByCurrentUser"], True)

    def test_observations_json_no_view_for_anonymous(self):
        """If the user is anonymous, there is NO data about which occurrences were already viewed"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=10&page_number=1")
        json_data = response.json()
        with self.assertRaises(KeyError):
            json_data["results"][0]["viewedByCurrentUser"]

    def test_observations_json_no_location(self):
        """Regression test: no error 500 in occurrences_json if we have locations without a location"""
        Observation.objects.create(
            gbif_id=4,
            occurrence_id="4",
            species=ApiTests.second_species,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.first_dataset,
            location=None,
        )
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=10&page_number=1")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 4)

    def test_observations_json_basic_no_filters(self):
        """Basic tests for the endpoint, no filters used"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")
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

    def test_observations_json_ordering_pk(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=10&page_number=1&order=-pk")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # Check that it's sorted by reverse primary key
        received_pks = [e["id"] for e in json_data["results"]]
        self.assertEqual(received_pks[::-1], sorted(received_pks))

    def test_observations_json_ordering_gbif_id(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # Check that it's sorted by GBIF id
        self.assertEqual(json_data["results"][0]["gbifId"], "1")
        self.assertEqual(json_data["results"][1]["gbifId"], "2")
        self.assertEqual(json_data["results"][2]["gbifId"], "3")

    def test_observations_json_ordering_species_name_asc(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(
            f"{base_url}?limit=10&page_number=1&order=species__name"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # Check that it's sorted by species name (alphabetical order)
        occ_species_names = [result["speciesName"] for result in json_data["results"]]
        self.assertEqual(occ_species_names, sorted(occ_species_names))

    def test_observations_json_ordering_species_name_desc(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(
            f"{base_url}?limit=10&page_number=1&order=-species__name"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # Check that it's sorted by species name (alphabetical order)
        occ_species_names = [result["speciesName"] for result in json_data["results"]]
        self.assertEqual(occ_species_names[::-1], sorted(occ_species_names))

    def test_observations_json_pagination_base(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")

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

    def test_observations_json_pagination_greater_than_max(self):
        """If the requested page number is greater than the number of pages, it returns the last page"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=2&page_number=3")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(len(json_data["results"]), 1)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 2)
        self.assertEqual(json_data["pageNumber"], 2)

    def test_observations_json_pagination_negative(self):
        """If the requested page number is negative, it returns the last page"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(f"{base_url}?limit=2&page_number=-5")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        self.assertEqual(len(json_data["results"]), 1)
        self.assertEqual(json_data["firstPage"], 1)
        self.assertEqual(json_data["lastPage"], 2)
        self.assertEqual(json_data["pageNumber"], 2)

    def test_observations_json_min_date_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(
            f"{base_url}?limit=10&page_number=1&startDate={OCTOBER_8_2021.strftime('%Y-%m-%d')}"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)
        self.assertEqual(json_data["results"][0]["gbifId"], "3")

    def test_observations_json_max_date_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        response = self.client.get(
            f"{base_url}?limit=10&page_number=1&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 2)
        self.assertIn(json_data["results"][0]["gbifId"], ["1", "2"])
        self.assertIn(json_data["results"][1]["gbifId"], ["1", "2"])

    def test_observations_json_species_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 2)
        self.assertIn(json_data["results"][0]["gbifId"], ["2", "3"])
        self.assertIn(json_data["results"][1]["gbifId"], ["2", "3"])

    def test_observations_json_dataset_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&datasetsIds[]={ApiTests.first_dataset.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 2)
        self.assertIn(json_data["results"][0]["gbifId"], ["1", "3"])
        self.assertIn(json_data["results"][1]["gbifId"], ["1", "3"])

    def test_observations_json_area_filter(self):
        """We filter by a single area"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&areaIds[]={ApiTests.global_area_andenne.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)
        self.assertEqual(
            json_data["results"][0]["gbifId"], "1"
        )  # Only one occurrence in Andenne because of the selected area

    def test_observations_json_multiple_areas_filter(self):
        """The areaIds parameter can take multiple values (OR)"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&areaIds[]={ApiTests.global_area_andenne.pk}&areaIds[]={ApiTests.global_area_lillois.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(
            json_data["totalResultsCount"], 3
        )  # All 3 occurrences should be there because the two areas cover them all

    def test_observations_json_multiple_datasets_filter_case1(self):
        """occurrences_json accept to filter per multiple datasets

        Case 1: Explicitly requests all datasets. Results should be the same than no filter"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")

        json_data_all_species = self.client.get(
            f"{base_url}?limit=10&page_number=1&datasetsIds[]={ApiTests.first_dataset.pk}&datasetsIds[]={ApiTests.second_dataset.pk}"
        ).json()
        json_data_no_species_filters = self.client.get(
            f"{base_url}?limit=10&page_number=1"
        ).json()
        self.assertEqual(json_data_all_species, json_data_no_species_filters)

    def test_observations_json_multiple_species_filter_case1(self):
        """occurrences_json accept to filter per multiple species

        Case 1: Explicitly requests all species. Results should be the same than no filter"""
        base_url = reverse("dashboard:api-filtered-observations-data-page")

        json_data_all_species = self.client.get(
            f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&speciesIds[]={ApiTests.first_species.pk}"
        ).json()
        json_data_no_species_filters = self.client.get(
            f"{base_url}?limit=10&page_number=1"
        ).json()
        self.assertEqual(json_data_all_species, json_data_no_species_filters)

    def test_observations_json_multiple_species_filter_case2(self):
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
        Observation.objects.create(
            gbif_id=1000,
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.first_dataset,
        )

        base_url = reverse("dashboard:api-filtered-observations-data-page")

        json_data = self.client.get(
            f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.first_species.pk}&speciesIds[]={species_tetraodon.pk}"
        ).json()

        self.assertEqual(json_data["totalResultsCount"], 2)
        for result in json_data["results"]:
            self.assertIn(
                result["speciesName"],
                [ApiTests.first_species.name, species_tetraodon.name],
            )

    def test_observations_json_multiple_dataset_filter_case2(self):
        """occurrences_json accept to filter per multiple datasets
        Case 2: request occurrences for datasets 1 and 3
        """
        # We need one more dataset and one related occurrence to perform this test
        third_dataset = Dataset.objects.create(
            name="Third dataset", gbif_dataset_key="xxxx"
        )
        Observation.objects.create(
            gbif_id=1000,
            species=ApiTests.first_species,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=third_dataset,
        )
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        json_data = self.client.get(
            f"{base_url}?limit=10&page_number=1&datasetsIds[]={ApiTests.first_dataset.pk}&datasetsIds[]={third_dataset.pk}"
        ).json()
        self.assertEqual(json_data["totalResultsCount"], 3)
        for result in json_data["results"]:
            self.assertIn(
                result["datasetName"],
                [ApiTests.first_dataset.name, third_dataset.name],
            )

    def test_observations_json_combined_filters(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)
        self.assertEqual(json_data["results"][0]["gbifId"], "2")

    def test_observations_json_combined_filters_case2(self):
        # Starting from test_observations_json_combined_filters, we add one dataset filter that won't change the results
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&endDate={yesterday.strftime('%Y-%m-%d')}&datasetsIds[]={ApiTests.second_dataset.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)
        self.assertEqual(json_data["results"][0]["gbifId"], "2")

    def test_observations_json_combined_filters_case3(self):
        # Starting from test_observations_json_combined_filters, we add one dataset filter => the filter combination now returns 0 results
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&datasetsIds[]={ApiTests.first_dataset.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 0)

    def test_observations_json_combined_filters_case4(self):
        # Starting from test_observations_json_combined_filters, we add one area filter that won't change the results
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&areaIds[]={ApiTests.global_area_lillois.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 1)

    def test_occurrence_json_combined_filters_case5(self):
        # Starting from test_observations_json_combined_filters, we add one area filter => the filter combination now returns 0 results
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.second_species.pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&areaIds[]={ApiTests.global_area_andenne.pk}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 0)

    def test_observations_json_no_results(self):
        base_url = reverse("dashboard:api-filtered-observations-data-page")
        url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={ApiTests.first_species.pk}&startDate={OCTOBER_8_2021.strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        json_data = response.json()
        self.assertEqual(json_data["totalResultsCount"], 0)
        self.assertEqual(json_data["results"], [])

    def test_observations_counter_no_filters(self):
        response = self.client.get(
            reverse("dashboard:api-filtered-observations-counter")
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 3)

    def test_observations_counter_species_filters(self):
        base_url = reverse("dashboard:api-filtered-observations-counter")
        url_with_params = f"{base_url}?speciesIds[]={ApiTests.second_species.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 2)

    def test_occurrence_counter_multiple_species_filter_case1(self):
        """We explicitly request all species: result should be identical to no species filtering"""
        base_url = reverse("dashboard:api-filtered-observations-counter")
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
        Observation.objects.create(
            gbif_id=1000,
            occurrence_id="1000",
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.first_dataset,
        )
        Observation.objects.create(
            gbif_id=1001,
            occurrence_id="1001",
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.first_dataset,
        )
        Observation.objects.create(
            gbif_id=1002,
            occurrence_id="1002",
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=ApiTests.di,
            source_dataset=ApiTests.first_dataset,
        )

        base_url = reverse("dashboard:api-filtered-observations-counter")
        json_data = self.client.get(
            f"{base_url}?speciesIds[]={ApiTests.second_species.pk}&speciesIds[]={species_tetraodon.pk}"
        ).json()
        self.assertEqual(json_data["count"], 5)

    def test_observations_counter_min_date_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-counter")
        url_with_params = f"{base_url}?startDate={OCTOBER_8_2021.strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 1)

    def test_observations_counter_area_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-counter")
        url_with_params = f"{base_url}?areaIds[]={ApiTests.global_area_andenne.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 1)

    def test_observations_counter_max_date_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-counter")
        url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 2)

    def test_observations_counter_combined_filters(self):
        """Counter is correct when filtering by species and end date"""
        base_url = reverse("dashboard:api-filtered-observations-counter")
        url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={ApiTests.second_species.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 1)

        # Case 2: we also add a dataset filter (which doesn't change the number of occurrences)
        url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={ApiTests.second_species.pk}&datasetsIds[]={ApiTests.second_dataset.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 1)

        # Case 3: we add another one, which brings the counter to zero
        url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={ApiTests.second_species.pk}&datasetsIds[]={ApiTests.first_dataset.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 0)

        # Case 4: start from case 1) but add an area filter that brings us to zero records
        url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={ApiTests.second_species.pk}&areaIds[]={ApiTests.global_area_andenne.pk}"
        response = self.client.get(url_with_params)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["count"], 0)

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

    def test_datasets_list_json(self):
        response = self.client.get(reverse("dashboard:api-datasets-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(len(json_data), 2)
        # Check the main fields are there (no KeyError exception)
        json_data[0]["name"]
        json_data[0]["id"]
        json_data[0]["gbifKey"]
        for entry in json_data:
            self.assertIn(entry["name"], ("Test dataset", "Test dataset #2"))

    def test_filtered_observations_monthly_histogram_json_no_filters(self):
        # case 1: no filters
        response = self.client.get(
            reverse("dashboard:api-filtered-observations-monthly-histogram")
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 2},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_end_date_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(f"{base_url}?endDate=2021-10-01")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 2},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_start_date_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(f"{base_url}?startDate=2021-10-01")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_species_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(
            f"{base_url}?speciesIds[]={ApiTests.second_species.pk}"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_combined_filters(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(
            f"{base_url}?speciesIds[]={ApiTests.second_species.pk}&endDate=2021-10-01"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_combined_filters_case2(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(
            f"{base_url}?areaIds[]={ApiTests.global_area_lillois.pk}&endDate=2021-10-01"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_dataset_filters(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(
            f"{base_url}?datasetsIds[]={ApiTests.first_dataset.pk}"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_area_filter(self):
        base_url = reverse("dashboard:api-filtered-observations-monthly-histogram")
        response = self.client.get(
            f"{base_url}?areaIds[]={ApiTests.global_area_andenne.pk}"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )
