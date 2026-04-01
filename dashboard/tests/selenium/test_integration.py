import datetime
import re
import time

from django.conf import settings
from django.test import tag
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait


from dashboard.models import (
    Species,
    DataImport,
    Dataset,
    Observation,
    Alert,
    ObservationUnseen,
    BasisOfRecord,
)
from dashboard.views.helpers import create_or_refresh_all_materialized_views


def _get_webdriver() -> WebDriver:
    # Selenium setup
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.browser_version = "113"  # Temporary workaround, new version throws tons of exceptions and I don't have the capacity to investigate right now
    if settings.SELENIUM_HEADLESS_MODE:
        options.add_argument("--headless")
    options.add_argument("--window-size=2560,1440")

    selenium = webdriver.Chrome(
        # service=ChromiumService(ChromeDriverManager(**chromedriver_args).install()),  # type: ignore
        options=options,
    )

    selenium.implicitly_wait(2)
    return selenium


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    GBIF_ALERT={
        "MAIN_MAP_CONFIG": {
            "initialZoom": 8,
            "initialLat": 50.50,
            "initialLon": 4.47,
        },
        "SITE_NAME": "LIFE RIPARIAS early alert",
        "PRIMEVUE_PRIMARY_PALETTE": "indigo",
        "ENABLED_LANGUAGES": ("en",),
    },
    DEBUG=True,
)
@tag("sequential")
class SeleniumTestsCommon(StaticLiveServerTestCase):
    """Common test data and Selenium-related plumbing"""

    @classmethod
    def setUpClass(cls):
        # Disable the Vite dev server so the pre-built bundle is used.
        # local_settings.py sets dev_mode=True for development; without the
        # Vite dev server running, Vue never mounts and the new navbar is absent.
        from django.conf import settings as _settings

        _settings.DJANGO_VITE["default"]["dev_mode"] = False
        from django_vite.core.asset_loader import DjangoViteAssetLoader  # type: ignore

        DjangoViteAssetLoader._instance = None

        super().setUpClass()
        cls.selenium = _get_webdriver()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

        # Restore Vite dev_mode so other test runs are not affected.
        from django.conf import settings as _settings

        _settings.DJANGO_VITE["default"]["dev_mode"] = True
        from django_vite.core.asset_loader import DjangoViteAssetLoader

        DjangoViteAssetLoader._instance = None

    def setUp(self):
        super().setUp()
        # Create test users
        User = get_user_model()
        normal_user = User.objects.create_user(
            username="testuser",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )
        adminuser = User.objects.create_superuser(
            username="adminuser", password="67890"
        )

        self.first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )
        self.second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064
        )

        di = DataImport.objects.create(start=timezone.now())

        self.first_dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )
        self.second_dataset = Dataset.objects.create(
            name="Test dataset #2",
            gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
        )

        self.basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")

        self.obs_1 = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=self.first_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=self.first_dataset,
            location=Point(5.09513, 50.48941, srid=4326),
            basis_of_record=self.basis_of_record,
        )
        self.obs_2 = Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=self.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),
            basis_of_record=self.basis_of_record,
        )
        self.obs_3 = Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=self.second_dataset,
            location=Point(5.09513, 50.48941, srid=4326),
            basis_of_record=self.basis_of_record,
        )

        # Obs 1 (and only obs_1) has been seen by the user
        ObservationUnseen.objects.create(observation=self.obs_1, user=adminuser)
        ObservationUnseen.objects.create(observation=self.obs_2, user=normal_user)
        ObservationUnseen.objects.create(observation=self.obs_2, user=adminuser)
        ObservationUnseen.objects.create(observation=self.obs_3, user=normal_user)
        ObservationUnseen.objects.create(observation=self.obs_3, user=adminuser)

        alert = Alert.objects.create(
            name="Test alert",
            user=normal_user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )

        alert.species.add(self.first_species)
        create_or_refresh_all_materialized_views()


class SeleniumTests(SeleniumTestsCommon):
    def test_signin_signout_scenario(self):
        # Navigate directly to the sign-in page
        # (navbar link visibility is covered by Playwright tests)
        self.selenium.get(self.live_server_url + "/accounts/signin/")

        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # We've never submitted the form, so we shouldn't have any error message
        with self.assertRaises(NoSuchElementException):
            self.selenium.find_element(By.ID, "gbif-alert-invalid-credentials-message")

        # There are required username and password fields
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        self.assertEqual(username_field.get_attribute("required"), "true")
        self.assertEqual(password_field.get_attribute("required"), "true")

        # There is also a link to find a lost password on this page
        self.selenium.find_element(By.LINK_TEXT, "Lost password?")

        # Trying to sign in with incorrect credentials
        username_field.clear()
        password_field.clear()
        username_field.send_keys("aaa")
        password_field.send_keys("bbb")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()

        # We're still on the same page, with an error message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element(
            By.ID, "gbif-alert-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )

        # Trying with a correct username but wrong password, we should be denied too
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("wrong_password")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element(
            By.ID, "gbif-alert-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )

        # Trying with correct credentials, we should be redirected to home page and properly logged
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we should be redirected to the home page
        wait.until(EC.title_contains("Home"))

        # Sign out via the signout URL
        # (navbar sign-out interaction is covered by Playwright tests)
        self.selenium.get(self.live_server_url + "/accounts/signout/")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))

    def test_signup_scenario_existing_username(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        self.selenium.get(self.live_server_url + "/signup")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element(By.ID, "id_username")
        email_field = self.selenium.find_element(By.ID, "id_email")
        password1_field = self.selenium.find_element(By.ID, "id_password1")
        password2_field = self.selenium.find_element(By.ID, "id_password2")
        signup_button = self.selenium.find_element(By.ID, "gbif-alert-signup-button")

        username_field.clear()
        username_field.send_keys("testuser")

        email_field.clear()
        email_field.send_keys("aaaa@bbb.com")

        password1_field.clear()
        password1_field.send_keys("FSDFSD981ç!")

        password2_field.clear()
        password2_field.send_keys("FSDFSD981ç!")

        signup_button.click()

        # We are still on the same page
        wait.until(EC.title_contains("Sign up"))
        # With a proper error message
        self.assertIn(
            "A user with that username already exists.", self.selenium.page_source
        )
        # No users were created
        self.assertEqual(number_users_before, User.objects.count())

    def test_signup_html5_form_validation(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        self.selenium.get(self.live_server_url + "/signup")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Get the elems
        username_field = self.selenium.find_element(By.ID, "id_username")
        first_name_field = self.selenium.find_element(By.ID, "id_first_name")
        last_name_field = self.selenium.find_element(By.ID, "id_last_name")
        email_field = self.selenium.find_element(By.ID, "id_email")
        password1_field = self.selenium.find_element(By.ID, "id_password1")
        password2_field = self.selenium.find_element(By.ID, "id_password2")
        signup_button = self.selenium.find_element(By.ID, "gbif-alert-signup-button")

        # Assert the proper fields are required
        self.assertEqual(username_field.get_attribute("required"), "true")
        self.assertEqual(email_field.get_attribute("required"), "true")
        self.assertEqual(password1_field.get_attribute("required"), "true")
        self.assertEqual(password2_field.get_attribute("required"), "true")
        self.assertIsNone(first_name_field.get_attribute("required"))
        self.assertIsNone(last_name_field.get_attribute("required"))

        # Assert the email field has the correct type (so browser will validate what it can)
        self.assertEqual(email_field.get_attribute("type"), "email")

        # If we click the button, no users are created
        signup_button.click()
        self.assertEqual(number_users_before, User.objects.count())

    def test_signup_scenario_password_dont_match(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        self.selenium.get(self.live_server_url + "/signup")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element(By.ID, "id_username")
        email_field = self.selenium.find_element(By.ID, "id_email")
        password1_field = self.selenium.find_element(By.ID, "id_password1")
        password2_field = self.selenium.find_element(By.ID, "id_password2")
        signup_button = self.selenium.find_element(By.ID, "gbif-alert-signup-button")

        username_field.clear()
        username_field.send_keys("testuser2")

        email_field.clear()
        email_field.send_keys("aaaa@bbb.com")

        password1_field.clear()
        password1_field.send_keys("FSDFSD981ç!")

        password2_field.clear()
        password2_field.send_keys("FSDFSD981ç!aaa")

        signup_button.click()

        # We are still on the same page
        wait.until(EC.title_contains("Sign up"))
        # With a proper error message
        self.assertIn(
            "The two password fields didn’t match.", self.selenium.page_source
        )
        # No users were created
        self.assertEqual(number_users_before, User.objects.count())

    def test_complete_signup_scenario_successful(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        self.selenium.get(self.live_server_url + "/signup")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element(By.ID, "id_username")
        email_field = self.selenium.find_element(By.ID, "id_email")
        password1_field = self.selenium.find_element(By.ID, "id_password1")
        password2_field = self.selenium.find_element(By.ID, "id_password2")
        signup_button = self.selenium.find_element(By.ID, "gbif-alert-signup-button")
        first_name_field = self.selenium.find_element(By.ID, "id_first_name")
        last_name_field = self.selenium.find_element(By.ID, "id_last_name")

        username_field.clear()
        username_field.send_keys("peterpan")

        first_name_field.clear()
        first_name_field.send_keys("Peter")

        last_name_field.clear()
        last_name_field.send_keys("Pan")

        email_field.clear()
        email_field.send_keys("peter@pan.com")

        password1_field.clear()
        password1_field.send_keys("kjdshfjksd678@")

        password2_field.clear()
        password2_field.send_keys("kjdshfjksd678@")

        signup_button.click()

        # We are redirected to the home page after signup
        wait.until(EC.title_contains("Home"))

        # A new user is added to the database
        self.assertEqual(number_users_before + 1, User.objects.count())

        # With the correct fields
        latest_created_user = User.objects.all().order_by("-id")[0]
        self.assertEqual(latest_created_user.username, "peterpan")
        self.assertEqual(latest_created_user.email, "peter@pan.com")
        self.assertEqual(latest_created_user.first_name, "Peter")
        self.assertEqual(latest_created_user.last_name, "Pan")
        self.assertFalse(latest_created_user.is_superuser)
        self.assertFalse(latest_created_user.is_staff)

        # Sign out via URL and sign in again with the chosen credentials
        self.selenium.get(self.live_server_url + "/accounts/signout/")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))

        # Navigate to sign-in and log back in
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("peterpan")
        password_field.send_keys("kjdshfjksd678@")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # We should be redirected to the home page
        wait.until(EC.title_contains("Home"))

        # All the existing observations are considered as seen by this new user
        existing_observations = Observation.objects.all()
        for obs in existing_observations:
            self.assertTrue(obs.already_seen_by(latest_created_user))

    def test_signup_too_common_password(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        self.selenium.get(self.live_server_url + "/signup")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element(By.ID, "id_username")
        email_field = self.selenium.find_element(By.ID, "id_email")
        password1_field = self.selenium.find_element(By.ID, "id_password1")
        password2_field = self.selenium.find_element(By.ID, "id_password2")
        signup_button = self.selenium.find_element(By.ID, "gbif-alert-signup-button")

        username_field.clear()
        username_field.send_keys("testuser2")

        email_field.clear()
        email_field.send_keys("aaaa@bbb.com")

        password1_field.clear()
        password1_field.send_keys("aaaaaaaa")

        password2_field.clear()
        password2_field.send_keys("aaaaaaaa")

        signup_button.click()

        # We are still on the same page
        wait.until(EC.title_contains("Sign up"))
        # With a proper error message
        self.assertIn("This password is too common.", self.selenium.page_source)
        # No users were created
        self.assertEqual(number_users_before, User.objects.count())

    def test_edit_profile_scenario(self):
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))

        # Navigate directly to the profile page
        self.selenium.get(self.live_server_url + "/profile")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("My profile"))

        # Basic checks on the form fields
        username_field = self.selenium.find_element(By.ID, "id_username")
        self.assertEqual(username_field.get_attribute("disabled"), "true")
        self.assertEqual(username_field.get_attribute("value"), "testuser")
        first_name_field = self.selenium.find_element(By.ID, "id_first_name")
        self.assertEqual(first_name_field.get_attribute("value"), "John")
        last_name_field = self.selenium.find_element(By.ID, "id_last_name")
        self.assertEqual(last_name_field.get_attribute("value"), "Frusciante")
        email_field = self.selenium.find_element(By.ID, "id_email")
        self.assertEqual(email_field.get_attribute("value"), "frusciante@gmail.com")
        delay_value_field = self.selenium.find_element(By.ID, "id_delay_value")
        delay_unit_select = Select(self.selenium.find_element(By.ID, "id_delay_unit"))
        # Users have one year of delay by default (365 days -> displayed as 1 year)
        self.assertEqual(delay_value_field.get_attribute("value"), "1")
        self.assertEqual(
            delay_unit_select.first_selected_option.get_attribute("value"), "years"
        )

        # Let's update the values
        first_name_field.clear()
        first_name_field.send_keys("Amanda")
        last_name_field.clear()
        last_name_field.send_keys("Palmer")
        email_field.clear()
        email_field.send_keys("palmer@gmail.com")
        delay_value_field.clear()
        delay_value_field.send_keys("1")
        delay_unit_select.select_by_value("months")  # 1 month = 30 days
        save_button = self.selenium.find_element(
            By.ID, "gbif-alert-profile-save-button"
        )
        save_button.click()

        # Check for the success message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))
        self.assertIn(
            "Your profile was successfully updated.", self.selenium.page_source
        )

        # Go to the profile again to check the values were updated
        self.selenium.get(self.live_server_url + "/profile")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("My profile"))

        username_field = self.selenium.find_element(By.ID, "id_username")
        self.assertEqual(username_field.get_attribute("value"), "testuser")
        first_name_field = self.selenium.find_element(By.ID, "id_first_name")
        self.assertEqual(first_name_field.get_attribute("value"), "Amanda")
        last_name_field = self.selenium.find_element(By.ID, "id_last_name")
        self.assertEqual(last_name_field.get_attribute("value"), "Palmer")
        email_field = self.selenium.find_element(By.ID, "id_email")
        self.assertEqual(email_field.get_attribute("value"), "palmer@gmail.com")
        delay_value_field = self.selenium.find_element(By.ID, "id_delay_value")
        delay_unit_select = Select(self.selenium.find_element(By.ID, "id_delay_unit"))
        # 30 days was saved, which rounds back to 1 month
        self.assertEqual(delay_value_field.get_attribute("value"), "1")
        self.assertEqual(
            delay_unit_select.first_selected_option.get_attribute("value"), "months"
        )

    def test_no_profile_page_if_not_logged(self):
        """We try to access the profile page directly from the URL, without being signed in"""
        self.selenium.get(self.live_server_url + "/profile")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(
            EC.url_contains("/accounts/signin/?next=/profile")
        )  # We are redirected to the login page

    def test_lost_password_scenario_wrong_address(self):
        # In this test we check that the password-reset feature works as expected
        # Case 1: email not linked to any account
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        lost_password_link = self.selenium.find_element(By.LINK_TEXT, "Lost password?")
        lost_password_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Forgot your password?"))
        email_address_field = self.selenium.find_element(By.ID, "id_email")
        email_address_field.clear()
        email_address_field.send_keys("wrong@address.com")

        send_me_instructions_button = self.selenium.find_element(
            By.ID, "gbif-alert-send-me-instructions-button"
        )
        send_me_instructions_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(
            EC.title_contains("Instructions sent")
        )  # We make it look it was successful, for security reasons
        # ... But no mail was sent
        self.assertEqual(len(mail.outbox), 0)

    def test_lost_password_scenario(self):
        # Case 2: successful password reset
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        lost_password_link = self.selenium.find_element(By.LINK_TEXT, "Lost password?")
        lost_password_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Forgot your password?"))
        email_address_field = self.selenium.find_element(By.ID, "id_email")
        email_address_field.clear()
        email_address_field.send_keys("frusciante@gmail.com")

        send_me_instructions_button = self.selenium.find_element(
            By.ID, "gbif-alert-send-me-instructions-button"
        )
        send_me_instructions_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Instructions sent"))
        # A mail was sent
        self.assertEqual(len(mail.outbox), 1)
        the_mail = mail.outbox[0]
        self.assertIn("Password reset on", the_mail.subject)
        self.assertListEqual(the_mail.to, ["frusciante@gmail.com"])
        pattern = r"http://[^\n]+"
        match = re.search(pattern, the_mail.body)
        reset_url = match.group(0)

        # Let's follow the link
        self.selenium.get(reset_url)
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Reset your password"))
        password1_field = self.selenium.find_element(By.ID, "id_new_password1")
        password2_field = self.selenium.find_element(By.ID, "id_new_password2")
        password1_field.clear()
        password1_field.send_keys("newpassword007")
        password2_field.clear()
        password2_field.send_keys("newpassword007")
        button = self.selenium.find_element(
            By.CSS_SELECTOR, "[value='Change my password']"
        )
        button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Password reset complete"))

        # Let's try the sign in
        signin_link = self.selenium.find_element(By.LINK_TEXT, "sign in")
        signin_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # First with the old password: this should fail
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        # We're still on the same page, with an error message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element(
            By.ID, "gbif-alert-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )

        # Now we retry with the new password, this should work!
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("newpassword007")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)
        # We should be redirected to the home page
        wait.until(EC.title_contains("Home"))

    def test_change_password_scenario(self):
        """A logged user wants to change his password"""
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Home"))

        # Navigate directly to the change password page
        self.selenium.get(self.live_server_url + "/accounts/password-change/")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Change my password"))

        old_password_field = self.selenium.find_element(By.ID, "id_old_password")
        new_password1_field = self.selenium.find_element(By.ID, "id_new_password1")
        new_password2_field = self.selenium.find_element(By.ID, "id_new_password2")
        submit_button = self.selenium.find_element(
            By.ID, "gbif-alert-change-password-submit-button"
        )

        # Failure case #1: wrong old password
        old_password_field.send_keys("wrongpassword")
        new_password1_field.send_keys("newpassword007")
        new_password2_field.send_keys("newpassword007")
        submit_button.click()

        # We stay on this same page, and see the error message
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Change my password"))
        self.assertIn(
            "Your old password was entered incorrectly. Please enter it again.",
            self.selenium.page_source,
        )

        # Failure case #2: new passwords don't match
        old_password_field = self.selenium.find_element(By.ID, "id_old_password")
        new_password1_field = self.selenium.find_element(By.ID, "id_new_password1")
        new_password2_field = self.selenium.find_element(By.ID, "id_new_password2")
        submit_button = self.selenium.find_element(
            By.ID, "gbif-alert-change-password-submit-button"
        )
        old_password_field.send_keys("12345")
        new_password1_field.send_keys("newpassword007")
        new_password2_field.send_keys("newpassword008")
        submit_button.click()
        # We stay on this same page, and see the error message
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Change my password"))
        self.assertIn(
            "The two password fields didn’t match.", self.selenium.page_source
        )

        # Success case
        old_password_field = self.selenium.find_element(By.ID, "id_old_password")
        new_password1_field = self.selenium.find_element(By.ID, "id_new_password1")
        new_password2_field = self.selenium.find_element(By.ID, "id_new_password2")
        submit_button = self.selenium.find_element(
            By.ID, "gbif-alert-change-password-submit-button"
        )
        old_password_field.send_keys("12345")
        new_password1_field.send_keys("newpassword007")
        new_password2_field.send_keys("newpassword007")
        submit_button.click()
        # We are redirected to another page, and see the success message

        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Password changed"))
        self.assertIn(
            "Your password was successfully changed.", self.selenium.page_source
        )

        # There's a link to go to the index page
        back_link = self.selenium.find_element(By.LINK_TEXT, "Go to index page")
        back_link.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Home"))

        # Sign out via URL and sign in again with the new password
        self.selenium.get(self.live_server_url + "/accounts/signout/")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Home"))

        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("newpassword007")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 3)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))

    def test_delete_account_scenario(self):
        """A user wants to delete his account, and need to confirm the action"""
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Home"))

        # Navigate directly to the profile page
        self.selenium.get(self.live_server_url + "/profile")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("My profile"))

        delete_account_button = self.selenium.find_element(
            By.ID, "gbif-alert-profile-delete-account-button"
        )
        delete_account_button.click()
        modal = self.selenium.find_element(By.CLASS_NAME, "modal")
        modal_title = modal.find_element(By.CLASS_NAME, "modal-title")
        self.assertEqual(modal_title.text, "Are you sure?")
        # Is the modal visible?
        self.assertIn("show", modal.get_attribute("class"))

        # Let's cancel the action
        cancel_button = modal.find_element(By.ID, "modal-button-no")
        cancel_button.click()

        # The modal should now be closed
        self.assertNotIn("show", modal.get_attribute("class"))

        # Let's open it again!
        delete_account_button.click()

        # Let's confirm the action
        confirm_button = modal.find_element(By.ID, "modal-button-yes")
        confirm_button.click()

        # We should now be redirected to the home page, with a proper message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))
        self.assertIn("Your account has been deleted.", self.selenium.page_source)

        # We should be visibly logged out (navbar state is covered by Playwright tests)
        # Let's try to sign in again...
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()

        # This is not possible anymore...
        # ... so we're still on the same page, with an error message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element(
            By.ID, "gbif-alert-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )
