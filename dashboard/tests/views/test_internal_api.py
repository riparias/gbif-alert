import datetime
import json
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    Area,
    Alert,
    ObservationUnseen,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()
OCTOBER_8_2021 = datetime.datetime.strptime("2021-10-08", "%Y-%m-%d").date()


class InternalApiAlertTests(TestCase):
    """Test the alert-related internal API endpoints"""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.first_user = User.objects.create_user(
            username="frusciante",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        cls.second_user = User.objects.create_user(
            username="other_user",
            password="12345",
            first_name="Aaa",
            last_name="Bbb",
            email="otheruser@gmail.com",
        )

        cls.first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )
        cls.second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064
        )

        cls.public_area_andenne = Area.objects.create(
            name="Public polygon - Andenne",
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

        cls.first_dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )

        cls.alert = Alert.objects.create(
            name="Test alert",
            user=cls.first_user,
            email_notifications_frequency="N",
        )
        cls.alert.species.add(cls.first_species)
        cls.alert.datasets.add(cls.first_dataset)
        cls.alert.areas.add(cls.public_area_andenne)

    def test_edit_alert_get(self):
        """GET requests return alert details so the form can be populated"""
        self.client.login(username="frusciante", password="12345")

        response = self.client.get(
            reverse("dashboard:internal-api:alert"),
            {"alert_id": self.alert.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.json(),
            {
                "areaIds": [self.public_area_andenne.pk],
                "datasetIds": [self.first_dataset.pk],
                "emailNotificationsFrequency": "N",
                "id": self.alert.pk,
                "name": "Test alert",
                "speciesIds": [self.first_species.pk],
            },
        )

    def _post_to_alert_endpoint(self, post_data: dict[str, Any]):
        return self.client.post(
            reverse("dashboard:internal-api:alert"),
            json.dumps(post_data),
            content_type="application/json",
        )

    def _assert_alert_endpoint_response(
        self, response, expected_response, expected_status_code=200
    ):
        self.assertEqual(response.status_code, expected_status_code)
        self.assertDictEqual(response.json(), expected_response)

    def _assert_alert_unchanged(self):
        """Assert that self.alert has not been changed"""
        before = self.alert.as_dict
        self.alert.refresh_from_db()
        self.assertDictEqual(before, self.alert.as_dict)

    def test_edit_alert_can_keep_name(self):
        """A user can edit its own alerts and keep the same name"""
        self.client.login(username="frusciante", password="12345")

        post_data = {
            "id": self.alert.pk,
            "name": "Test alert",
            "speciesIds": [s.pk for s in self.alert.species.all()],
            "areaIds": [a.pk for a in self.alert.areas.all()],
            "datasetIds": [d.pk for d in self.alert.datasets.all()],
            "emailNotificationsFrequency": self.alert.email_notifications_frequency,
        }
        response = self._post_to_alert_endpoint(post_data)

        self._assert_alert_endpoint_response(
            response, {"alertId": self.alert.pk, "errors": {}, "success": True}
        )

    def test_edit_alert_cannot_duplicate_names(self):
        """A user cannot edit its own alerts and use the same name as another alert"""

        Alert.objects.create(name="Test alert 2", user=self.first_user)

        self.client.login(username="frusciante", password="12345")
        post_data = {
            "id": self.alert.pk,
            "name": "Test alert 2",
            "speciesIds": [s.pk for s in self.alert.species.all()],
            "areaIds": [a.pk for a in self.alert.areas.all()],
            "datasetIds": [d.pk for d in self.alert.datasets.all()],
            "emailNotificationsFrequency": self.alert.email_notifications_frequency,
        }
        response = self._post_to_alert_endpoint(post_data)

        self._assert_alert_endpoint_response(
            response,
            {
                "alertId": self.alert.pk,
                "errors": {
                    "__all__": ["Alert with this User and Name already exists."]
                },
                "success": False,
            },
        )

        self._assert_alert_unchanged()

    def test_edit_alert_no_duplicate_names_issues_between_users(self):
        """Duplicate alert names are allowed between users"""
        Alert.objects.create(name="Test alert 2", user=self.second_user)

        self.client.login(username="frusciante", password="12345")
        post_data = {
            "id": self.alert.pk,
            "name": "Test alert 2",
            "speciesIds": [s.pk for s in self.alert.species.all()],
            "areaIds": [a.pk for a in self.alert.areas.all()],
            "datasetIds": [d.pk for d in self.alert.datasets.all()],
            "emailNotificationsFrequency": self.alert.email_notifications_frequency,
        }
        response = self._post_to_alert_endpoint(post_data)

        self._assert_alert_endpoint_response(
            response, {"alertId": self.alert.pk, "errors": {}, "success": True}
        )

    def test_edit_alert_cannot_edit_other_users_alerts(self):
        self.client.login(username="other_user", password="12345")

        post_data = {
            "id": self.alert.pk,
            "name": "New alert name",
            "speciesIds": [
                self.first_species.pk,
                self.second_species.pk,
            ],  # Add a species
            "areaIds": [],  # Remove the area
            "datasetIds": [],  # Remove the dataset
            "emailNotificationsFrequency": "M",
        }

        response = self._post_to_alert_endpoint(post_data)

        # Check the response
        self.assertEqual(response.status_code, 404)

        self._assert_alert_unchanged()

    def test_edit_alert_species_mandatory(self):
        self.client.login(username="frusciante", password="12345")

        post_data = {
            "id": self.alert.pk,
            "name": self.alert.name,
            "speciesIds": [],  # Attempt to remove all species
            "areaIds": [a.pk for a in self.alert.areas.all()],
            "datasetIds": [d.pk for d in self.alert.datasets.all()],
            "emailNotificationsFrequency": "M",
        }

        response = self._post_to_alert_endpoint(post_data)

        self._assert_alert_endpoint_response(
            response,
            {
                "alertId": self.alert.pk,
                "errors": {"species": ["At least one species must be selected"]},
                "success": False,
            },
        )

        self._assert_alert_unchanged()

    def test_edit_alert_name_mandatory(self):
        self.client.login(username="frusciante", password="12345")

        post_data = {
            "id": self.alert.pk,
            "name": "",  # Attempt to remove name
            "speciesIds": [s.pk for s in self.alert.species.all()],
            "areaIds": [a.pk for a in self.alert.areas.all()],
            "datasetIds": [d.pk for d in self.alert.datasets.all()],
            "emailNotificationsFrequency": "M",
        }

        response = self._post_to_alert_endpoint(post_data)

        self._assert_alert_endpoint_response(
            response,
            {
                "alertId": self.alert.pk,
                "errors": {"name": ["This field cannot be blank."]},
                "success": False,
            },
        )

        self._assert_alert_unchanged()

    def test_edit_alert_success(self):
        """A user can edit its own alerts"""
        self.client.login(username="frusciante", password="12345")

        post_data = {
            "id": self.alert.pk,
            "name": "New alert name",
            "speciesIds": [
                self.first_species.pk,
                self.second_species.pk,
            ],  # Add a species
            "areaIds": [],  # Remove the area
            "datasetIds": [],  # Remove the dataset
            "emailNotificationsFrequency": "M",
        }

        response = self._post_to_alert_endpoint(post_data)

        # Check the response
        self._assert_alert_endpoint_response(
            response, {"alertId": self.alert.pk, "errors": {}, "success": True}
        )

        # Check the alert was updated in the database
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.name, "New alert name")
        self.assertEqual(self.alert.email_notifications_frequency, "M")
        self.assertEqual(self.alert.species.count(), 2)
        self.assertEqual(self.alert.datasets.count(), 0)
        self.assertEqual(self.alert.areas.count(), 0)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class InternalApiTests(TestCase):
    """Test the rest of the internal API endpoints"""

    @classmethod
    def setUpTestData(cls):
        cls.first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )
        cls.second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064
        )

        mocked = datetime.datetime(2022, 2, 11, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            cls.di = DataImport.objects.create(start=timezone.now())

        cls.first_dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )
        cls.second_dataset = Dataset.objects.create(
            name="Test dataset #2",
            gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
        )

        cls.obs1 = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=cls.first_species,
            date=SEPTEMBER_13_2021,
            data_import=cls.di,
            initial_data_import=cls.di,
            source_dataset=cls.first_dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )
        cls.obs2 = Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=cls.second_species,
            date=SEPTEMBER_13_2021,
            data_import=cls.di,
            initial_data_import=cls.di,
            source_dataset=cls.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )
        cls.obs3 = Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=cls.second_species,
            date=OCTOBER_8_2021,
            data_import=cls.di,
            initial_data_import=cls.di,
            source_dataset=cls.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )

        cls.public_area_andenne = Area.objects.create(
            name="Public polygon - Andenne",
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

        cls.public_area_lillois = Area.objects.create(
            name="Public polygon - Lillois",
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

        # Initial situation: only obs2 has been seen by "another user"
        ObservationUnseen.objects.create(observation=cls.obs1, user=cls.area_owner)
        ObservationUnseen.objects.create(observation=cls.obs1, user=cls.another_user)
        ObservationUnseen.objects.create(observation=cls.obs2, user=cls.area_owner)
        ObservationUnseen.objects.create(observation=cls.obs3, user=cls.area_owner)
        ObservationUnseen.objects.create(observation=cls.obs3, user=cls.another_user)

    def test_dataimports_list_json(self):
        """Simple tests for the API that serves the list of dataimport objects"""
        response = self.client.get(
            reverse("dashboard:internal-api:dataimports-list-json")
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        di_id = self.di.pk
        self.assertEqual(
            json_data,
            [
                {
                    "id": di_id,
                    "name": f"Data import #{di_id}",
                    "startTimestamp": "2022-02-11T15:10:00Z",
                }
            ],
        )

    def test_areas_list_json_anonymous(self):
        """Getting the list of areas as an anonymous user"""
        response = self.client.get(reverse("dashboard:internal-api:areas-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Make sure we only get the public ones
        self.assertEqual(len(json_data), 2)

        for the_area in json_data:
            self.assertTrue(the_area["name"].startswith("Public polygon"))
            self.assertFalse(the_area["isUserSpecific"])

    def test_areas_list_json_owner(self):
        """Getting the list of areas as an authenticated user that has a personal area"""
        self.client.login(username="frusciante", password="12345")
        response = self.client.get(reverse("dashboard:internal-api:areas-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Make sure we get public ones, but also the user-specific one
        self.assertEqual(len(json_data), 3)
        for area in json_data:
            self.assertIn(
                area["name"],
                (
                    "Public polygon - Andenne",
                    "Public polygon - Lillois",
                    "User polygon",
                ),
            )

    def test_areas_list_json_otheruser(self):
        """Getting the list of areas as an authenticated user that as NO personal area

        (result should be identical to test_areas_list_json_anonymous())
        """
        self.client.login(username="frusciante1", password="12345")
        response = self.client.get(reverse("dashboard:internal-api:areas-list-json"))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Make sure we only get the public ones
        self.assertEqual(len(json_data), 2)

        for the_area in json_data:
            self.assertTrue(the_area["name"].startswith("Public polygon - "))
            self.assertFalse(the_area["isUserSpecific"])

    def test_area_geojson_anonymous(self):
        """Anonymous users can get the public areas, not the user-specific ones"""

        # Case 1: we request a public area
        response = self.client.get(
            reverse(
                "dashboard:internal-api:area-geojson",
                kwargs={"id": self.public_area_andenne.pk},
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
            reverse(
                "dashboard:internal-api:area-geojson",
                kwargs={"id": self.user_area.pk},
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"")

    def test_area_geojson_owner(self):
        """The area owner can get the public areas, but also its own"""

        self.client.login(username="frusciante", password="12345")
        # Case 1: we request the public area
        response = self.client.get(
            reverse(
                "dashboard:internal-api:area-geojson",
                kwargs={"id": self.public_area_andenne.pk},
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
            reverse(
                "dashboard:internal-api:area-geojson",
                kwargs={"id": self.user_area.pk},
            )
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
                "dashboard:internal-api:area-geojson",
                kwargs={"id": self.public_area_andenne.pk},
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
            reverse(
                "dashboard:internal-api:area-geojson",
                kwargs={"id": self.user_area.pk},
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"")

    def test_datasets_list_json(self):
        response = self.client.get(reverse("dashboard:internal-api:datasets-list-json"))
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
            reverse("dashboard:internal-api:filtered-observations-monthly-histogram")
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
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?endDate=2021-10-01")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 2},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_start_date_filter(self):
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?startDate=2021-10-01")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_species_filter(self):
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?speciesIds[]={self.second_species.pk}")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_status_filter_invalid_value(
        self,
    ):
        self.client.login(username="frusciante1", password="12345")
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?status=klfhjklsdwfhklsfhs")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 2},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_status_filter_case1(self):
        self.client.login(username="frusciante1", password="12345")
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?status=seen")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_status_filter_case2(self):
        self.client.login(username="frusciante1", password="12345")
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?status=unseen")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_status_filter_anonymous(self):
        """Anonymous users: the status filter is ignored"""
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?status=unseen")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 2},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_combined_filters(self):
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(
            f"{base_url}?speciesIds[]={self.second_species.pk}&endDate=2021-10-01"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_combined_filters_case2(self):
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(
            f"{base_url}?areaIds[]={self.public_area_lillois.pk}&endDate=2021-10-01"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_combined_filters_case3(self):
        self.client.login(username="frusciante1", password="12345")
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(
            f"{base_url}?speciesIds[]={self.second_species.pk}&endDate=2021-10-01&status=seen"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_combined_filters_case4(self):
        self.client.login(username="frusciante1", password="12345")
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(
            f"{base_url}?speciesIds[]={self.second_species.pk}&endDate=2021-10-01&status=unseen"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(response.content.decode("utf-8"), [])

    def test_filtered_observations_monthly_histogram_json_dataset_filters(self):
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(f"{base_url}?datasetsIds[]={self.first_dataset.pk}")
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
                {"year": 2021, "month": 10, "count": 1},
            ],
        )

    def test_filtered_observations_monthly_histogram_json_area_filter(self):
        base_url = reverse(
            "dashboard:internal-api:filtered-observations-monthly-histogram"
        )
        response = self.client.get(
            f"{base_url}?areaIds[]={self.public_area_andenne.pk}"
        )
        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content.decode("utf-8"),
            [
                {"year": 2021, "month": 9, "count": 1},
            ],
        )
