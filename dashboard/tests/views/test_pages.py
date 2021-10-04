import datetime

from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import Occurrence, Species, DataImport, Dataset


class WebPagesTests(TestCase):
    def test_homepage(self):
        """There's a Bootstrap-powered page at /"""
        response = self.client.get("/")
        self.assertContains(response, "bootstrap.min.css", status_code=200)
        self.assertContains(response, "container")
        self.assertTemplateUsed(response, "dashboard/index.html")

    def test_occurrence_details_not_found(self):
        response = self.client.get(
            reverse("dashboard:occurrence-details", kwargs={"pk": 1000})
        )
        self.assertEqual(response.status_code, 404)

    def test_occurrence_details(self):
        occ = Occurrence.objects.create(
            gbif_id=1,
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=Dataset.objects.create(
                name="Test dataset", gbif_id="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
            ),
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        response = self.client.get(
            reverse("dashboard:occurrence-details", kwargs={"pk": occ.pk})
        )
        self.assertEqual(response.status_code, 200)

        # A few checks on the basic content
        self.assertContains(response, '<a href="https://www.gbif.org/occurrence/1">')
