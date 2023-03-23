import datetime

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dashboard.models import (
    Species,
    Dataset,
    Alert,
    Observation,
    DataImport,
    ObservationComment,
    ObservationView,
    User,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class ActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.user = User.objects.create_user(
            username="frusciante",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        cls.alert = Alert.objects.create(
            user=cls.user,
        )

        di = DataImport.objects.create(start=timezone.now())

        cls.observation = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=Species.objects.create(
                name="Procambarus fallax", gbif_taxon_key=8879526
            ),
            date=SEPTEMBER_13_2021,
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
            ),
            location=Point(5.09513, 50.48941, srid=4326),
        )

        cls.user_comment = ObservationComment.objects.create(
            author=cls.user,
            observation=cls.observation,
            text="This is a first comment",
        )

        cls.observation_view = ObservationView.objects.create(
            observation=cls.observation, user=cls.user
        )

    def test_delete_own_account_success(self):
        """
        Test that a user can delete his own account

        Related entities should be deleted as well (comments, views, alerts, ...)
        The session is terminated and the user is redirected to the home page with a proper message
        """
        self.client.login(username="frusciante", password="12345")
        response = self.client.post(reverse("dashboard:actions:delete-own-account"))
        # We got redirected to the index page with the proper message
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Your account has been deleted.")
        # The user has been signed out
        self.assertNotIn("_auth_user_id", self.client.session)
        # Entities have been removed in the database
        with self.assertRaises(User.DoesNotExist):
            self.user.refresh_from_db()
        with self.assertRaises(Alert.DoesNotExist):
            self.alert.refresh_from_db()
        with self.assertRaises(ObservationView.DoesNotExist):
            self.observation_view.refresh_from_db()

        self.user_comment.refresh_from_db()
        self.assertEqual(self.user_comment.author, None)
        self.assertEqual(self.user_comment.text, "")
        self.assertTrue(self.user_comment.emptied_because_author_deleted_account)

    def test_delete_own_account_anonymous(self):
        """
        Test that an anonymous user cannot delete his account and receive a proper HTTP 403
        """
        response = self.client.post(reverse("dashboard:actions:delete-own-account"))
        self.assertEqual(response.status_code, 403)
