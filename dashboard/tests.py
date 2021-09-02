from django.test import TestCase
from django.urls import reverse


class WebPagesTests(TestCase):
    def test_homepage(self):
        """There's a Bootstrap-powered page at /"""
        response = self.client.get("/")
        self.assertContains(response, "bootstrap.min.css", status_code=200)
        self.assertContains(response, "container")
        self.assertTemplateUsed(response, "dashboard/index.html")


class ApiTests(TestCase):
    def test_species_list_json(self):
        response = self.client.get(reverse("dashboard:api-species-list-json"))
        self.assertEqual(response.status_code, 200)
        # There's already 18 entries in the species table thanks to a data migration (0002_populate_initial_species.py)

        json_data = response.json()
        self.assertEqual(len(json_data), 18)

        # Check the main fields are there (no KeyError exception)
        json_data[0]["name"]
        json_data[0]["id"]
        json_data[0]["gbif_taxon_key"]

        # Check a specific one can be found
        found = False
        for entry in json_data:
            if entry["name"] == "Elodea nuttallii":
                found = True
                break

        self.assertTrue(found)
