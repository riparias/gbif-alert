import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point
from django.utils import timezone, formats
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
            individual_count=2,
            locality="Andenne centre",
            municipality="Andenne",
            recorded_by="Nicolas Noé",
            basis_of_record="HUMAN_OBSERVATION",
            coordinate_uncertainty_in_meters=10,
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
        self.assertContains(
            response, "<b>Species: </b><i>Elodea nuttallii</i>", html=True
        )
        self.assertContains(response, "<b>Individual count: </b> 2", html=True)
        self.assertContains(response, "<b>Source dataset: </b> Test dataset", html=True)
        self.assertContains(
            response, "<b>Basis of record: </b> HUMAN_OBSERVATION", html=True
        )
        self.assertContains(
            response,
            f"<b>Date: </b>{formats.date_format(WebPagesTests.first_occ.date, 'DATE_FORMAT')}",
            html=True,
        )
        self.assertContains(
            response,
            "<b>Coordinates: </b> (5.095129999999999, 50.48940999999999)",
            html=True,
        )
        self.assertContains(response, "<b>Municipality: </b> Andenne", html=True)
        self.assertContains(response, "<b>Locality: </b> Andenne centre", html=True)
        self.assertContains(response, "<b>Recorded by: </b> Nicolas Noé", html=True)
        self.assertContains(
            response, "<b>Coordinates uncertainty: </b> 10.0 meters", html=True
        )

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

    def test_occurrence_details_attempt_to_post_comment_not_logged(self):
        """We attempt to post a comment without being authenticated, that doesn't work"""
        occurrence = self.__class__.second_occ

        number_comments_before = OccurrenceComment.objects.filter(
            occurrence=occurrence
        ).count()

        response = self.client.post(
            reverse(
                "dashboard:page-occurrence-details",
                kwargs={"stable_id": occurrence.stable_id},
            ),
            {"text": "This is my comment"},
        )

        number_comments_after = OccurrenceComment.objects.filter(
            occurrence=occurrence
        ).count()

        self.assertEqual(response.status_code, 403)  # Access denied
        self.assertEqual(number_comments_after, number_comments_before)

    def test_occurrence_details_attempt_to_post_comment_logged(self):
        """We attempt to post a comment (authenticated this time), that should work"""
        occurrence = self.__class__.second_occ

        number_comments_before = OccurrenceComment.objects.filter(
            occurrence=occurrence
        ).count()

        self.client.login(username="frusciante", password="12345")
        response = self.client.post(
            reverse(
                "dashboard:page-occurrence-details",
                kwargs={"stable_id": occurrence.stable_id},
            ),
            {"text": "New comment from the test suite"},
        )

        number_comments_after = OccurrenceComment.objects.filter(
            occurrence=occurrence
        ).count()

        self.assertEqual(response.status_code, 200)  # HTTP success
        self.assertEqual(
            number_comments_after, number_comments_before + 1
        )  # One new comment for the occurrence in DB
        self.assertTemplateUsed(
            response, "dashboard/occurrence_details.html"
        )  # On the occurrence details page
        self.assertContains(
            response, "New comment from the test suite"
        )  # The comment appears in the page
