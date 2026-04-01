import datetime
import json
import re
from unittest import mock
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, formats
from django.utils.html import strip_tags

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    BasisOfRecord,
    ObservationComment,
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
class WebPagesTests(TestCase):
    """Various web page tests  # TODO: split in multiple classes?"""

    @classmethod
    def setUpTestData(cls):
        dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )

        basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")

        di = DataImport.objects.create(start=timezone.now())

        cls.first_obs = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=Species.objects.create(
                name="Procambarus fallax", gbif_taxon_key=8879526
            ),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            individual_count=2,
            locality="Andenne centre",
            municipality="Andenne",
            recorded_by="Nicolas Noé",
            basis_of_record=basis_of_record,
            coordinate_uncertainty_in_meters=10,
            references="https://www.google.com",
        )

        cls.second_obs = Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=Species.objects.create(
                name="Orconectes virilis",
                gbif_taxon_key=2227064,
            ),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=basis_of_record,
            references="this is not an URL",
        )

        User = get_user_model()
        cls.comment_author = User.objects.create_user(
            username="frusciante",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        # Let's force an earlier date for auto_add_now
        mocked = datetime.datetime(2018, 4, 4, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            ObservationComment.objects.create(
                observation=cls.second_obs,
                author=cls.comment_author,
                text="This is my comment",
            )

            ObservationComment.objects.create(
                observation=cls.second_obs,
                author=None,
                text="",
                emptied_because_author_deleted_account=True,
            )

            # ObservationView.objects.create(
            #     observation=cls.second_obs, user=comment_author
            # )

    def test_observation_details_not_found(self):
        response = self.client.get(
            reverse("dashboard:pages:observation-details", kwargs={"stable_id": 1000})
        )
        self.assertEqual(response.status_code, 404)

    def test_observation_details_base(self):
        obs_stable_id = self.first_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        self.assertIn(obs_stable_id, page_url)
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)

        # A few checks on the basic content
        self.assertContains(response, '<a href="https://www.gbif.org/occurrence/1">')
        self.assertContains(
            response, "<dt>Species</dt><dd><i>Procambarus fallax</i></dd>", html=True
        )
        self.assertContains(response, "<dt>Individual count</dt><dd>2</dd>", html=True)
        self.assertContains(
            response,
            '<dt>Source dataset</dt><dd><a href="https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e">Test dataset</a></dd>',
            html=True,
        )
        self.assertContains(
            response, "<dt>Basis of record</dt><dd>HUMAN_OBSERVATION</dd>", html=True
        )
        self.assertContains(
            response,
            f"<dt>Date</dt><dd>{formats.date_format(self.first_obs.date, 'DATE_FORMAT')}</dd>",
            html=True,
        )
        self.assertContains(
            response,
            "<dt>Coordinates</dt><dd>5.095129999999999, 50.48940999999999</dd>",
            html=True,
        )
        self.assertContains(
            response, "<dt>Municipality</dt><dd>Andenne</dd>", html=True
        )
        self.assertContains(
            response, "<dt>Locality</dt><dd>Andenne centre</dd>", html=True
        )
        self.assertContains(
            response, "<dt>Recorded by</dt><dd>Nicolas Noé</dd>", html=True
        )

    def test_observation_details_references_formatted(self):
        """Check the 'references' field is properly formatted"""

        di = DataImport.objects.create(start=timezone.now())
        new_obs = Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=Species.objects.create(name="AAA BBB", gbif_taxon_key=22),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="azerty",
            ),
            location=Point(5.09513, 50.48941, srid=4326),
            basis_of_record=BasisOfRecord.objects.get_or_create(name="HUMAN_OBSERVATION")[0],
        )

        # case 1: no references is data: field is not shown
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": new_obs.stable_id},
            )
        )

        self.assertNotContains(response, "<dt>References</dt>", html=True)

        # case 2: reference is a URL, it is displayed in a clickable format
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": self.first_obs.stable_id},
            )
        )

        self.assertContains(
            response,
            '<dt>References</dt><dd><a href="https://www.google.com">https://www.google.com</a></dd>',
            html=True,
        )

        # case 3: Reference is a string, displayed without a link
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": self.second_obs.stable_id},
            )
        )

        self.assertNotContains(
            response,
            '<dt>References</dt><dd><a href="this is not an URL">this is not an URL</a></dd>',
            html=True,
        )

        self.assertContains(
            response,
            "<dt>References</dt><dd>this is not an URL</dd>",
            html=True,
        )

    def test_observation_details_coordinates_uncertainty_format(self):
        """Check we have a nice display in various cases"""
        di = DataImport.objects.create(start=timezone.now())
        new_obs = Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=Species.objects.create(name="AAA BBB", gbif_taxon_key=22),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="azerty",
            ),
            location=Point(5.09513, 50.48941, srid=4326),
            basis_of_record=BasisOfRecord.objects.get_or_create(name="HUMAN_OBSERVATION")[0],
        )

        # case 1: coordinates uncertainty unknown
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": new_obs.stable_id},
            )
        )

        self.assertContains(
            response,
            """<dt>Coordinates uncertainty</dt>
               <dd> unknown<br><small><i class="bi bi-info-circle"></i> represented as a 100m <b>red</b> circle</small></dd>""",
            html=True,
        )

        # case 2: 1 meter => singular value
        new_obs.coordinate_uncertainty_in_meters = 1
        new_obs.save()
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": new_obs.stable_id},
            )
        )

        self.assertContains(
            response,
            """<dt>Coordinates uncertainty</dt>
               <dd> 1 meter<br><small><i class="bi bi-info-circle"></i> the <b>green circle</b> accurately represents the coordinates uncertainty</small></dd>""",
            html=True,
        )

        # case 2: 3 meters => plural value
        new_obs.coordinate_uncertainty_in_meters = 3
        new_obs.save()
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": new_obs.stable_id},
            )
        )

        self.assertContains(
            response,
            """<dt>Coordinates uncertainty</dt>
               <dd> 3 meters<br><small><i class="bi bi-info-circle"></i> the <b>green circle</b> accurately represents the coordinates uncertainty</small></dd>""",
            html=True,
        )

        # case 3: 5 meters => do not display ".0" when not necessary
        new_obs.coordinate_uncertainty_in_meters = 5.0
        new_obs.save()
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": new_obs.stable_id},
            )
        )

        self.assertContains(
            response,
            """<dt>Coordinates uncertainty</dt>
               <dd> 5 meters<br><small><i class="bi bi-info-circle"></i> the <b>green circle</b> accurately represents the coordinates uncertainty</small></dd>""",
            html=True,
        )

        # case 4: display 1 decimal place when necessary:
        new_obs.coordinate_uncertainty_in_meters = 3.141592
        new_obs.save()
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": new_obs.stable_id},
            )
        )

        self.assertContains(
            response,
            """<dt>Coordinates uncertainty</dt>
               <dd> 3.1 meters<br><small><i class="bi bi-info-circle"></i> the <b>green circle</b> accurately represents the coordinates uncertainty</small></dd>""",
            html=True,
        )

    def test_observation_details_comments_empty(self):
        """A message is shown if no comment for the observation"""
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": self.first_obs.stable_id},
            )
        )

        self.assertContains(response, "No comments yet for this observation!")

    def test_observation_details_comment(self):
        """Observation comments are displayed"""
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": self.second_obs.stable_id},
            )
        )

        # There's 2 comments on this page, one "normal" one and one "emptied" (author account deleted)
        self.assertContains(
            response,
            '<p class="small text-muted">by <em>frusciante</em> on April 4, 2018, 2 a.m.</p>',
            html=True,
        )
        self.assertContains(response, "This is my comment", html=True)

        self.assertContains(
            response,
            '<p class="small text-muted">by <em>[deleted user]</em> on April 4, 2018, 2 a.m.</p><p><em>[deleted comment]</em></p>',
            html=True,
        )

        # TODO: test with more details (ordering, ...)

    def test_observation_details_comment_post_not_logged(self):
        """Non-logged users are invited to sign in to post comments"""
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": self.second_obs.stable_id},
            )
        )
        self.assertIn(
            "Please sign in to be able to post comments.", strip_tags(response.content)
        )

    def test_observation_details_attempt_to_post_comment_not_logged(self):
        """We attempt to post a comment without being authenticated, that doesn't work"""
        observation = self.second_obs

        number_comments_before = ObservationComment.objects.filter(
            observation=observation
        ).count()

        response = self.client.post(
            reverse(
                "dashboard:pages:observation-details",
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
        observation = self.second_obs

        number_comments_before = ObservationComment.objects.filter(
            observation=observation
        ).count()

        self.client.login(username="frusciante", password="12345")
        response = self.client.post(
            reverse(
                "dashboard:pages:observation-details",
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
        obs_stable_id = self.first_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertNotContains(response, "You have first seen this observation on")
        self.assertNotContains(response, "Mark this observation as unseen")

    def test_observation_details_observation_view_authenticated_not_in_alerts(self):
        """Visiting the observation_details page while logged in: there's no button to mark as unseen because the user has no matchin alert for the observation"""
        self.client.login(username="frusciante", password="12345")
        obs_stable_id = self.first_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertNotContains(response, "Mark this observation as unseen")

    def test_observation_details_observation_view_authenticated_in_alerts(self):
        """Same as before, but this time the user has an alert that matches the observation, so the link is displayed"""
        alert = Alert.objects.create(
            name="Test alert",
            user=self.comment_author,
            email_notifications_frequency="N",
        )
        alert.species.add(self.first_obs.species)

        self.client.login(username="frusciante", password="12345")
        obs_stable_id = self.first_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertContains(response, "Mark this observation as unseen")


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
