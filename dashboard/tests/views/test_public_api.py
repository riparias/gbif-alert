from django.test import TestCase, override_settings
from django.urls import reverse

from dashboard.models import Species


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class PublicApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )
        cls.second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064
        )

    def test_species_list_json(self):
        """Basic tests on the endpoint: status, length, content, ..."""
        response = self.client.get(reverse("dashboard:public-api:species-list-json"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")

        json_data = response.json()
        self.assertEqual(len(json_data), 2)

        # Check the main fields are there (no KeyError exception)
        json_data[0]["scientificName"]
        json_data[0]["id"]
        json_data[0]["gbifTaxonKey"]

        # Check a specific one can be found
        found = False
        for entry in json_data:
            if entry["scientificName"] == "Procambarus fallax":
                found = True
                break

        self.assertTrue(found)

    def test_species_list_cors_enabled(self):
        """Make sure CORS is enabled for the (semi public) species_list JSON API

        # Technique inspired from https://stackoverflow.com/a/47609921
        """
        request_headers = {
            "HTTP_ACCESS_CONTROL_REQUEST_METHOD": "GET",
            "HTTP_ORIGIN": "http://somethingelse.com",
        }
        response = self.client.get(
            reverse("dashboard:public-api:species-list-json"), {}, **request_headers
        )
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
