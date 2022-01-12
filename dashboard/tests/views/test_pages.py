import datetime
from unittest import mock

import pytz
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point
from django.utils import timezone, formats
from django.utils.html import strip_tags

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationComment,
    ObservationView,
)


class WebPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )

        cls.first_obs = Observation.objects.create(
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

        cls.second_obs = Observation.objects.create(
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

        ObservationComment.objects.create(
            observation=cls.second_obs, author=comment_author, text="This is my comment"
        )

        # Let's force an earlier date for auto_add_now
        mocked = datetime.datetime(2018, 4, 4, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            ObservationView.objects.create(
                observation=cls.second_obs, user=comment_author
            )

    def test_homepage(self):
        """There's a Bootstrap-powered page at /"""
        response = self.client.get("/")
        self.assertContains(response, "bootstrap.min.css", status_code=200)
        self.assertContains(response, "container")
        self.assertTemplateUsed(response, "dashboard/index.html")

    def test_observation_details_not_found(self):
        response = self.client.get(
            reverse("dashboard:page-observation-details", kwargs={"stable_id": 1000})
        )
        self.assertEqual(response.status_code, 404)

    def test_observation_details_base(self):
        obs_stable_id = self.__class__.first_obs.stable_id

        page_url = reverse(
            "dashboard:page-observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        self.assertIn(obs_stable_id, page_url)
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
            f"<b>Date: </b>{formats.date_format(self.__class__.first_obs.date, 'DATE_FORMAT')}",
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

    def test_observation_details_comments_empty(self):
        """A message is shown if no comment for the observation"""
        response = self.client.get(
            reverse(
                "dashboard:page-observation-details",
                kwargs={"stable_id": self.__class__.first_obs.stable_id},
            )
        )

        self.assertContains(response, "No comments yet for this observation!")

    def test_observation_details_comment(self):
        """Observation comments are displayed"""
        response = self.client.get(
            reverse(
                "dashboard:page-observation-details",
                kwargs={"stable_id": self.__class__.second_obs.stable_id},
            )
        )

        self.assertContains(response, "by frusciante on")
        self.assertContains(response, "This is my comment")
        # TODO: test with more details (multiple comments, ordering, ...)

    def test_observation_details_comment_post_not_logged(self):
        """Non-logged users are invited to sign in to post comments"""
        response = self.client.get(
            reverse(
                "dashboard:page-observation-details",
                kwargs={"stable_id": self.__class__.second_obs.stable_id},
            )
        )
        self.assertIn(
            "Please sign in to be able to post comments.", strip_tags(response.content)
        )

    def test_observation_details_attempt_to_post_comment_not_logged(self):
        """We attempt to post a comment without being authenticated, that doesn't work"""
        observation = self.__class__.second_obs

        number_comments_before = ObservationComment.objects.filter(
            observation=observation
        ).count()

        response = self.client.post(
            reverse(
                "dashboard:page-observation-details",
                kwargs={"stable_id": observation.stable_id},
            ),
            {"text": "This is my comment"},
        )

        number_comments_after = ObservationComment.objects.filter(
            observation=observation
        ).count()

        self.assertEqual(response.status_code, 403)  # Access denied
        self.assertEqual(number_comments_after, number_comments_before)

    def test_observation_details_attempt_to_post_comment_logged(self):
        """We attempt to post a comment (authenticated this time), that should work"""
        observation = self.__class__.second_obs

        number_comments_before = ObservationComment.objects.filter(
            observation=observation
        ).count()

        self.client.login(username="frusciante", password="12345")
        response = self.client.post(
            reverse(
                "dashboard:page-observation-details",
                kwargs={"stable_id": observation.stable_id},
            ),
            {"text": "New comment from the test suite"},
        )

        number_comments_after = ObservationComment.objects.filter(
            observation=observation
        ).count()

        self.assertEqual(response.status_code, 200)  # HTTP success
        self.assertEqual(
            number_comments_after, number_comments_before + 1
        )  # One new comment for the observation in DB
        self.assertTemplateUsed(
            response, "dashboard/observation_details.html"
        )  # On the observation details page
        self.assertContains(
            response, "New comment from the test suite"
        )  # The comment appears in the page

    def test_observation_details_observation_view_anonymous(self):
        """Visiting the observation details page anonymously: no 'first seen' timestamp, nor button to mark as not seen"""
        obs_stable_id = self.__class__.first_obs.stable_id

        page_url = reverse(
            "dashboard:page-observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertNotContains(response, "You have first seen this observation on")
        self.assertNotContains(response, "Mark as not viewed")

    def test_observation_details_observation_view_authenticated_case_1(self):
        """Visiting the observation_details page while logged in: there's a first seen timestamp, and a button to mark as unseen

        In this case, this is the first time we see the observation, so the timestamp is very recent
        """
        self.client.login(username="frusciante", password="12345")
        obs_stable_id = self.__class__.first_obs.stable_id

        page_url = reverse(
            "dashboard:page-observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertContains(response, "You have first seen this observation on")
        self.assertContains(response, "Mark as not viewed")
        timestamp = response.context["first_view_by_user_timestamp"]
        self.assertLess(timezone.now() - timestamp, datetime.timedelta(minutes=1))

    def test_observation_details_observation_view_authenticated_case_2(self):
        """Visiting the observation_details page while logged in: there's a first seen timestamp, and a button to mark as unseen

        In this case, the user show a previously seen observation: timestamp is older
        """
        self.client.login(username="frusciante", password="12345")
        obs_stable_id = self.__class__.second_obs.stable_id

        page_url = reverse(
            "dashboard:page-observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertContains(response, "You have first seen this observation on")
        self.assertContains(response, "Mark as not viewed")
        timestamp = response.context["first_view_by_user_timestamp"]
        self.assertEqual(timestamp.year, 2018)
        self.assertEqual(timestamp.month, 4)
        self.assertEqual(timestamp.day, 4)
