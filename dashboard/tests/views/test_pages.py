import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.html import strip_tags

from dashboard.models import Occurrence, Species, DataImport, Dataset, OccurrenceComment


class WebPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )

        cls.first_occ = Occurrence.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=Species.objects.all()[0],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        cls.second_occ = Occurrence.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=Species.objects.all()[1],
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            source_dataset=dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        User = get_user_model()
        comment_author = User.objects.create_user(
            username="frusciante",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        OccurrenceComment.objects.create(
            occurrence=cls.second_occ, author=comment_author, text="This is my comment"
        )

    def test_homepage(self):
        """There's a Bootstrap-powered page at /"""
        response = self.client.get("/")
        self.assertContains(response, "bootstrap.min.css", status_code=200)
        self.assertContains(response, "container")
        self.assertTemplateUsed(response, "dashboard/index.html")

    def test_occurrence_details_not_found(self):
        response = self.client.get(
            reverse("dashboard:page-occurrence-details", kwargs={"stable_id": 1000})
        )
        self.assertEqual(response.status_code, 404)

    def test_occurrence_details_base(self):
        occ_stable_id = self.__class__.first_occ.stable_id

        page_url = reverse(
            "dashboard:page-occurrence-details",
            kwargs={"stable_id": occ_stable_id},
        )

        self.assertIn(occ_stable_id, page_url)
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)

        # A few checks on the basic content
        self.assertContains(response, '<a href="https://www.gbif.org/occurrence/1">')

    def test_occurrence_details_comments_empty(self):
        """A message is shown if no comment for the occurrence"""
        response = self.client.get(
            reverse(
                "dashboard:page-occurrence-details",
                kwargs={"stable_id": self.__class__.first_occ.stable_id},
            )
        )

        self.assertContains(response, "No comments yet for this occurrence!")

    def test_occurrence_details_comment(self):
        """Occurrence comments are displayed"""
        response = self.client.get(
            reverse(
                "dashboard:page-occurrence-details",
                kwargs={"stable_id": self.__class__.second_occ.stable_id},
            )
        )

        self.assertContains(response, "by frusciante on")
        self.assertContains(response, "This is my comment")
        # TODO: test with more details (multiple comments, ordering, ...)

    def test_occurrence_details_comment_post_not_logged(self):
        """Non-logged users are invited to sign in to post comments"""
        response = self.client.get(
            reverse(
                "dashboard:page-occurrence-details",
                kwargs={"stable_id": self.__class__.second_occ.stable_id},
            )
        )
        self.assertIn(
            "Please sign in to be able to post comments.", strip_tags(response.content)
        )
