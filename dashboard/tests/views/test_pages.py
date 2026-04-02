import json
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase, override_settings
from django.urls import reverse

from dashboard.models import (
    Species,
    Dataset,
    Alert,
    Area,
)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class IndexPageTests(TestCase):
    """Tests for the home/index page"""

    def test_index_base(self):
        """The Vue SPA shell is served at /"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/base.html")


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class AlertWebPagesTests(TestCase):
    """Alert-related web page tests - pages now serve the Vue SPA shell."""

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

        cls.first_user_area = Area.objects.create(
            name="First user polygon",
            owner=cls.first_user,
            mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
        )

        cls.second_user_area = Area.objects.create(
            name="Second user polygon",
            owner=cls.second_user,
            mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
        )

    def test_user_can_access_own_alert_details(self):
        """Authenticated user gets the SPA shell for their alert detail page."""
        self.client.login(username="frusciante", password="12345")
        page_url = reverse("dashboard:pages:alert-details", kwargs={"alert_id": self.alert.id})
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/base.html")

    def test_anonymous_cant_access_alert_details(self):
        """An anonymous user is redirected to sign in when trying to see alert details."""
        page_url = reverse("dashboard:pages:alert-details", kwargs={"alert_id": self.alert.id})
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 302)

    def test_otheruser_cant_access_alert_details(self):
        """An authenticated user cannot see another user's alert detail page."""
        self.client.login(username="other_user", password="12345")
        page_url = reverse("dashboard:pages:alert-details", kwargs={"alert_id": self.alert.id})
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 404)

    def test_user_can_access_alert_create_page(self):
        """Authenticated user gets the SPA shell for the alert create page."""
        self.client.login(username="frusciante", password="12345")
        response = self.client.get(reverse("dashboard:pages:alert-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/base.html")

    def test_anonymous_cant_access_alert_create(self):
        """Anonymous user is redirected when accessing alert create page."""
        response = self.client.get(reverse("dashboard:pages:alert-create"))
        self.assertEqual(response.status_code, 302)

    def test_user_can_access_alert_edit_page(self):
        """Authenticated user gets the SPA shell for their alert edit page."""
        self.client.login(username="frusciante", password="12345")
        page_url = reverse("dashboard:pages:alert-edit", kwargs={"alert_id": self.alert.id})
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/base.html")

    def test_otheruser_cant_access_alert_edit(self):
        """Another user cannot access alert edit page."""
        self.client.login(username="other_user", password="12345")
        page_url = reverse("dashboard:pages:alert-edit", kwargs={"alert_id": self.alert.id})
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_cant_access_alert_edit(self):
        """Anonymous user is redirected when accessing alert edit page."""
        page_url = reverse("dashboard:pages:alert-edit", kwargs={"alert_id": self.alert.id})
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 302)

    def test_user_can_access_my_alerts_page(self):
        """Authenticated user gets the SPA shell for the my-alerts page."""
        self.client.login(username="frusciante", password="12345")
        response = self.client.get(reverse("dashboard:pages:my-alerts"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/base.html")

    def test_anonymous_cant_access_my_alerts(self):
        """Anonymous user is redirected when accessing my-alerts."""
        response = self.client.get(reverse("dashboard:pages:my-alerts"))
        self.assertEqual(response.status_code, 302)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class NavConfigJsonTests(TestCase):
    """Tests for the nav_config_json template tag and the JSON it injects into every page.

    The Vue navbar reads this JSON at mount time. These tests verify that the
    server-side data layer produces the correct structure - the rendering itself
    is covered by the Playwright tests in dashboard/tests/playwright/test_navbar.py.
    """

    _NAV_CONFIG_RE = re.compile(
        r'id="gbif-alert-nav-config"[^>]*>(.*?)</script>', re.DOTALL
    )

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.regular_user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        cls.superuser = User.objects.create_superuser(
            username="admin", password="adminpass123", email="admin@example.com"
        )

    def _get_nav_config(self, response):
        """Parse and return the nav config JSON embedded in the page."""
        content = response.content.decode()
        match = self._NAV_CONFIG_RE.search(content)
        self.assertIsNotNone(match, "gbif-alert-nav-config script tag not found in response")
        return json.loads(match.group(1))

    # --- Structural ---

    def test_json_present_on_every_page(self):
        """The nav config script tag is present on every page that uses base.html."""
        for url in ["/", reverse("dashboard:pages:news")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'id="gbif-alert-nav-config"')

    def test_required_url_keys(self):
        """All URL keys the Vue navbar expects are present."""
        response = self.client.get("/")
        config = self._get_nav_config(response)
        expected_keys = {
            "index", "news", "myAlerts", "aboutSite", "aboutData",
            "profile", "passwordChange", "myCustomAreas", "signout",
            "signin", "signup", "admin", "setLanguage",
        }
        self.assertEqual(set(config["urls"].keys()), expected_keys)

    # --- Anonymous user ---

    def test_anonymous_user_fields(self):
        """Anonymous users produce isAuthenticated=false, null username, all flags false."""
        response = self.client.get("/")
        user_data = self._get_nav_config(response)["user"]
        self.assertFalse(user_data["isAuthenticated"])
        self.assertIsNone(user_data["username"])
        self.assertFalse(user_data["isSuperuser"])
        self.assertFalse(user_data["hasUnseenNews"])
        self.assertFalse(user_data["hasAlertsWithUnseenObservations"])

    # --- Authenticated regular user ---

    def test_authenticated_user_fields(self):
        """Authenticated users get isAuthenticated=true and their username."""
        self.client.login(username="testuser", password="testpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertTrue(user_data["isAuthenticated"])
        self.assertEqual(user_data["username"], "testuser")
        self.assertFalse(user_data["isSuperuser"])

    @patch("dashboard.models.User.has_unseen_news", True)
    def test_has_unseen_news_true(self):
        """hasUnseenNews is true when the user has unseen news."""
        self.client.login(username="testuser", password="testpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertTrue(user_data["hasUnseenNews"])

    @patch("dashboard.models.User.has_unseen_news", False)
    def test_has_unseen_news_false(self):
        """hasUnseenNews is false when the user has no unseen news."""
        self.client.login(username="testuser", password="testpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertFalse(user_data["hasUnseenNews"])

    @patch("dashboard.models.User.has_alerts_with_unseen_observations", True)
    def test_has_unseen_observations_true(self):
        """hasAlertsWithUnseenObservations is true when the user has unseen observations."""
        self.client.login(username="testuser", password="testpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertTrue(user_data["hasAlertsWithUnseenObservations"])

    @patch("dashboard.models.User.has_alerts_with_unseen_observations", False)
    def test_has_unseen_observations_false(self):
        """hasAlertsWithUnseenObservations is false when the user has no unseen observations."""
        self.client.login(username="testuser", password="testpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertFalse(user_data["hasAlertsWithUnseenObservations"])

    # --- Theme ---

    def test_primary_palette_field(self):
        """primaryPalette is present in the nav config and is a non-empty string."""
        response = self.client.get("/")
        config = self._get_nav_config(response)
        self.assertIn("primaryPalette", config)
        self.assertIsInstance(config["primaryPalette"], str)
        self.assertTrue(config["primaryPalette"])

    # --- Superuser ---

    def test_superuser_flag(self):
        """isSuperuser is true for superusers, false for regular users."""
        self.client.login(username="admin", password="adminpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertTrue(user_data["isSuperuser"])

        self.client.login(username="testuser", password="testpass123")
        user_data = self._get_nav_config(self.client.get("/"))["user"]
        self.assertFalse(user_data["isSuperuser"])
