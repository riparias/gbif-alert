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
    ObservationUnseen,
    User,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()


class ActionAlertTests(TestCase):
    """Alert-related action tests"""

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

    def test_delete_alert_anonymous(self):
        """An anonymous user cannot delete an alert"""
        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": self.alert.pk},
        )
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in
        self.assertEqual(response.url, "/accounts/signin/?next=/actions/delete_alert")

    def test_delete_alert_success(self):
        """A user can delete its own alerts"""
        self.client.login(username="frusciante", password="12345")

        # Situation before: there's an alert for this user
        self.assertEqual(Alert.objects.filter(user=self.first_user).count(), 1)

        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": self.alert.pk},
        )
        # No more alerts for this user
        self.assertEqual(Alert.objects.filter(user=self.first_user).count(), 0)

        # The user gets redirected to the "my alerts" page
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in
        self.assertEqual(response.url, "/my-alerts")

    def test_delete_non_existing_alert(self):
        """We get an error 404 when trying to delete an alert that doesn't exist"""
        self.client.login(username="frusciante", password="12345")

        # Situation before: there's an alert for this user
        self.assertEqual(Alert.objects.filter(user=self.first_user).count(), 1)

        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": 5},
        )
        # The user alert has been untouched
        self.assertEqual(Alert.objects.filter(user=self.first_user).count(), 1)

        self.assertEqual(response.status_code, 404)

    def test_delete_other_user_alert(self):
        """A user cannot delete an alert owned by someone else"""
        self.client.login(username="other_user", password="12345")

        # Situation before: there's an alert for this user
        self.assertEqual(Alert.objects.all().count(), 1)

        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": self.alert.pk},
        )
        # Alerts are unchanged in the database
        self.assertEqual(Alert.objects.all().count(), 1)

        self.assertEqual(response.status_code, 403)


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

        cls.observation_unseen_obj = ObservationUnseen.objects.create(
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
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            self.observation_unseen_obj.refresh_from_db()

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
