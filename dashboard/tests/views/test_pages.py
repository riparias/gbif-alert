import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.utils import timezone, formats
from django.utils.html import strip_tags

from dashboard.models import (
    Observation,
    Species,
    DataImport,
    Dataset,
    ObservationComment,
    ObservationView,
    Alert,
    Area,
)


class AlertWebPagesTests(TestCase):
    """Alerts-related web page tests"""

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

        second_user = User.objects.create_user(
            username="other_user",
            password="12345",
            first_name="Aaa",
            last_name="Bbb",
            email="otheruser@gmail.com",
        )

        cls.first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526, group="CR"
        )
        cls.second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064, group="CR"
        )

        cls.public_area_andenne = Area.objects.create(
            name="Public polygon - Andenne",
            # Covers Namur-Liège area (includes Andenne but not Lillois)
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
            user=cls.first_user,
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
            owner=second_user,
            mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
        )

    my_alerts_navbar_snippet = '<a class="nav-link " aria-current="page" href="/my-alerts"><i class="bi bi-exclamation-square"></i>My alerts</a>'

    def test_navbar_my_alerts_authenticated(self):
        """Authenticated users have a 'my alerts' link in the navbar"""
        self.client.login(username="frusciante", password="12345")
        response = self.client.get("/")
        self.assertContains(
            response,
            self.my_alerts_navbar_snippet,
            html=True,
        )

    def test_navbar_my_alerts_anonymous(self):
        """Anonymous users **don't** have a 'my alerts' link in the navbar"""
        response = self.client.get("/")
        self.assertNotContains(
            response,
            self.my_alerts_navbar_snippet,
            html=True,
        )

    def test_user_can_access_own_alert_details(self):
        """An authenticated user has access to details of their own alerts"""
        self.client.login(username="frusciante", password="12345")
        page_url = reverse(
            "dashboard:pages:alert-details",
            kwargs={"alert_id": self.__class__.alert.id},
        )
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)

    def test_anonymous_cant_access_alert_details(self):
        """An anonymous user is invited to log in when trying to see an alert details"""
        page_url = reverse(
            "dashboard:pages:alert-details",
            kwargs={"alert_id": self.__class__.alert.id},
        )
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in

    def test_otheruser_cant_access_alert_details(self):
        """An authenticated user cannot see the alert details of another user"""
        self.client.login(username="other_user", password="12345")
        page_url = reverse(
            "dashboard:pages:alert-details",
            kwargs={"alert_id": self.__class__.alert.id},
        )
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cant_access_new_alert_page(self):
        """Anonymous users cannot access the create alert page"""
        # 1) GET
        response = self.client.get(reverse("dashboard:pages:alert-create"))
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in
        self.assertEqual(response.url, "/accounts/signin/?next=/new-alert")

        # 2) POST
        response = self.client.post(reverse("dashboard:pages:alert-create"))
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in
        self.assertEqual(response.url, "/accounts/signin/?next=/new-alert")

    def test_get_new_alert_page(self):
        """An authenticated has a page allowing to create an alert"""
        self.client.login(username="frusciante", password="12345")

        response = self.client.get(reverse("dashboard:pages:alert-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/alert_create.html")

        # The template receives a form, with a species selector that shows 2 entries (all species)
        self.assertEqual(
            len(response.context["form"].fields["species"].choices.queryset), 2
        )

        # Same thing for datasets (only 1 in database)
        self.assertEqual(
            len(response.context["form"].fields["datasets"].choices.queryset), 1
        )

        # Areas: the user can select the public ones, as well as their own (but not those owned by someone else)
        self.assertEqual(
            len(response.context["form"].fields["areas"].choices.queryset), 2
        )
        available_area_names = [
            a[1] for a in response.context["form"].fields["areas"].choices
        ]
        self.assertIn("Public polygon - Andenne", available_area_names)
        self.assertIn("First user polygon", available_area_names)
        self.assertNotIn("Second user polygon", available_area_names)

        # Let's make sure we also have a submit button that targets the same view
        self.assertIn('<form method="post">', response.content.decode())
        self.assertContains(
            response,
            '<input class="btn btn-primary" type="submit" value="Create alert">',
            html=True,
        )

    def test_post_new_alert_page(self):
        self.client.login(username="frusciante", password="12345")

        # Attempt 1: post no data: we stay on the same page because there's one field required (email_notifications_frequency)
        response = self.client.post(reverse("dashboard:pages:alert-create"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["form"].errors), 1)
        self.assertIn("email_notifications_frequency", response.context["form"].errors)
        # No new alert was created in the database
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 1
        )

        # Attempt 2: post email_notifications_frequency: the alerts gets created and the user is redirected to the alert details page
        response = self.client.post(
            reverse("dashboard:pages:alert-create"),
            {"email_notifications_frequency": "D"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/alert/2")
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 2
        )
        # Values check:
        new_alert = Alert.objects.get(pk=2)
        self.assertEqual(new_alert.user, self.__class__.first_user)
        self.assertEqual(new_alert.email_notifications_frequency, "D")
        self.assertEqual(new_alert.areas.count(), 0)
        self.assertEqual(new_alert.species.count(), 0)
        self.assertEqual(new_alert.datasets.count(), 0)

        # Attempt 3: post all fields: the alerts gets created and the user is redirected to the alert details page
        response = self.client.post(
            reverse("dashboard:pages:alert-create"),
            {
                "email_notifications_frequency": "W",
                "species": [
                    self.__class__.first_species.pk,
                    self.__class__.second_species.pk,
                ],
                "datasets": self.__class__.first_dataset.pk,
                "areas": self.__class__.public_area_andenne.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/alert/3")
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 3
        )

        new_alert = Alert.objects.get(pk=3)
        self.assertEqual(new_alert.user, self.__class__.first_user)
        self.assertEqual(new_alert.email_notifications_frequency, "W")
        self.assertEqual(new_alert.areas.count(), 1)
        self.assertEqual(new_alert.areas.first().name, "Public polygon - Andenne")
        self.assertEqual(new_alert.species.count(), 2)
        new_alert_species_name = [s.name for s in new_alert.species.all()]
        self.assertIn("Procambarus fallax", new_alert_species_name)
        self.assertIn("Orconectes virilis", new_alert_species_name)
        self.assertEqual(new_alert.datasets.count(), 1)
        self.assertEqual(new_alert.datasets.first().name, "Test dataset")

    def test_delete_alert_anonymous(self):
        """An anonymous user cannot delete an alert"""
        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": self.__class__.alert.pk},
        )
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in
        self.assertEqual(response.url, "/accounts/signin/?next=/actions/delete_alert")

    def test_delete_alert_success(self):
        """A user can delete its own alerts"""
        self.client.login(username="frusciante", password="12345")

        # Situation before: there's an alert for this user
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 1
        )

        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": self.__class__.alert.pk},
        )
        # No more alerts for this user
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 0
        )

        # The user gets redirected to the "my alerts" page
        self.assertEqual(response.status_code, 302)  # We got redirected to sign in
        self.assertEqual(response.url, "/my-alerts")

    def test_delete_non_existing_alert(self):
        """We get an error 404 when trying to delete an alert that doesn't exist"""
        self.client.login(username="frusciante", password="12345")

        # Situation before: there's an alert for this user
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 1
        )

        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": 5},
        )
        # The user alert has been untouched
        self.assertEqual(
            Alert.objects.filter(user=self.__class__.first_user).count(), 1
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_other_user_alert(self):
        """A user cannot delete an alert owned by someone else"""
        self.client.login(username="other_user", password="12345")

        # Situation before: there's an alert for this user
        self.assertEqual(Alert.objects.all().count(), 1)

        response = self.client.post(
            reverse("dashboard:actions:delete-alert"),
            {"alert_id": self.__class__.alert.pk},
        )
        # Alerts are unchanged in the database
        self.assertEqual(Alert.objects.all().count(), 1)

        self.assertEqual(response.status_code, 403)


class WebPagesTests(TestCase):
    """Various web page tests  # TODO: split in multiple classes?"""

    @classmethod
    def setUpTestData(cls):
        dataset = Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        )

        di = DataImport.objects.create(start=timezone.now())

        cls.first_obs = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=Species.objects.create(
                name="Procambarus fallax", gbif_taxon_key=8879526, group="CR"
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
            basis_of_record="HUMAN_OBSERVATION",
            coordinate_uncertainty_in_meters=10,
            references="https://www.google.com",
        )

        cls.second_obs = Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=Species.objects.create(
                name="Orconectes virilis", gbif_taxon_key=2227064, group="CR"
            ),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            references="this is not an URL",
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
        mocked = datetime.datetime(2018, 4, 4, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            ObservationView.objects.create(
                observation=cls.second_obs, user=comment_author
            )

    def test_homepage(self):
        """There's a Bootstrap-powered page at /"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "container")
        self.assertTemplateUsed(response, "dashboard/index.html")

    def test_observation_details_not_found(self):
        response = self.client.get(
            reverse("dashboard:pages:observation-details", kwargs={"stable_id": 1000})
        )
        self.assertEqual(response.status_code, 404)

    def test_observation_details_base(self):
        obs_stable_id = self.__class__.first_obs.stable_id

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
            response, "<dt>Source dataset</dt><dd>Test dataset</dd>", html=True
        )
        self.assertContains(
            response, "<dt>Basis of record</dt><dd>HUMAN_OBSERVATION</dd>", html=True
        )
        self.assertContains(
            response,
            f"<dt>Date</dt><dd>{formats.date_format(self.__class__.first_obs.date, 'DATE_FORMAT')}</dd>",
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
            species=Species.objects.create(
                name="AAA BBB", gbif_taxon_key=22, group="CR"
            ),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="azerty",
            ),
            location=Point(5.09513, 50.48941, srid=4326),
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
                kwargs={"stable_id": self.__class__.first_obs.stable_id},
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
                kwargs={"stable_id": self.__class__.second_obs.stable_id},
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
            species=Species.objects.create(
                name="AAA BBB", gbif_taxon_key=22, group="CR"
            ),
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="azerty",
            ),
            location=Point(5.09513, 50.48941, srid=4326),
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
                kwargs={"stable_id": self.__class__.first_obs.stable_id},
            )
        )

        self.assertContains(response, "No comments yet for this observation!")

    def test_observation_details_comment(self):
        """Observation comments are displayed"""
        response = self.client.get(
            reverse(
                "dashboard:pages:observation-details",
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
                "dashboard:pages:observation-details",
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
        observation = self.__class__.second_obs

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
        obs_stable_id = self.__class__.first_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertNotContains(response, "You have first seen this observation on")
        self.assertNotContains(response, "Mark this observation as unseen")

    def test_observation_details_observation_view_authenticated_case_1(self):
        """Visiting the observation_details page while logged in: there's a first seen timestamp, and a button to mark as unseen

        In this case, this is the first time we see the observation, so the timestamp is very recent
        """
        self.client.login(username="frusciante", password="12345")
        obs_stable_id = self.__class__.first_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertContains(response, "You have first seen this observation on")
        self.assertContains(response, "Mark this observation as unseen")
        timestamp = response.context["first_seen_by_user_timestamp"]
        self.assertLess(timezone.now() - timestamp, datetime.timedelta(minutes=1))

    def test_observation_details_observation_view_authenticated_case_2(self):
        """Visiting the observation_details page while logged in: there's a first seen timestamp, and a button to mark as unseen

        In this case, the user show a previously seen observation: timestamp is older
        """
        self.client.login(username="frusciante", password="12345")
        obs_stable_id = self.__class__.second_obs.stable_id

        page_url = reverse(
            "dashboard:pages:observation-details",
            kwargs={"stable_id": obs_stable_id},
        )

        response = self.client.get(page_url)
        self.assertContains(response, "You have first seen this observation on")
        self.assertContains(response, "Mark this observation as unseen")
        timestamp = response.context["first_seen_by_user_timestamp"]
        self.assertEqual(timestamp.year, 2018)
        self.assertEqual(timestamp.month, 4)
        self.assertEqual(timestamp.day, 4)
