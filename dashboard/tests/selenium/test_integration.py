import datetime
import time

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from selenium import webdriver  # type: ignore
from selenium.common.exceptions import NoSuchElementException  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.select import Select  # type: ignore
from selenium.webdriver.support.wait import WebDriverWait  # type: ignore
from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
from webdriver_manager.core.utils import ChromeType  # type: ignore

from dashboard.models import (
    Species,
    DataImport,
    Dataset,
    Observation,
    ObservationView,
    Alert,
)

HEADLESS_MODE = True


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class PteroisSeleniumTestsCommon(StaticLiveServerTestCase):
    """Common test data and Selenium-related plumbing"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Selenium setup
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        if HEADLESS_MODE:
            options.add_argument("--headless")
        options.add_argument("--window-size=2560,1440")
        cls.selenium = webdriver.Chrome(
            ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install(),
            options=options,
        )
        cls.selenium.implicitly_wait(2)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

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
        User.objects.create_superuser(username="adminuser", password="67890")

        first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526, group="CR"
        )
        second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064, group="CR"
        )

        di = DataImport.objects.create(start=timezone.now())

        first_dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )
        second_dataset = Dataset.objects.create(
            name="Test dataset #2",
            gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
        )

        obs_1 = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=first_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=first_dataset,
            location=Point(5.09513, 50.48941, srid=4326),
        )
        Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=second_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),
        )
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=second_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=second_dataset,
            location=Point(5.09513, 50.48941, srid=4326),
        )

        # Obs 1 (and only obs_1) has been seen by the user
        ObservationView.objects.create(observation=obs_1, user=normal_user)

        Alert.objects.create(
            name="Test alert",
            user=normal_user,
            email_notifications_frequency=Alert.DAILY_EMAILS,
        )


class PteroisSeleniumAlertTests(PteroisSeleniumTestsCommon):
    """Integration tests for the alert-related features"""

    def test_alert_edit_cancel_scenario(self):
        """The user go to the edit alert page, but change its mind and cancel"""
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        navbar.find_element_by_link_text("My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single edit alert button (only one alert)
        edit_buttons = self.selenium.find_elements_by_class_name(
            "pterois-edit-alert-button"
        )
        self.assertEqual(len(edit_buttons), 1)
        edit_button = edit_buttons[0]
        edit_button.click()
        WebDriverWait(self.selenium, 3)

        # Om the edit alert page, let's click the cancel button and make sure we go back to the alerts list
        cancel_button = self.selenium.find_element_by_link_text("Cancel")
        cancel_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("My alerts"))

    def test_alert_edit_scenario(self):
        """The user go to the edit alert page, make edits and save them"""
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        navbar.find_element_by_link_text("My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single edit alert button (only one alert)
        edit_buttons = self.selenium.find_elements_by_class_name(
            "pterois-edit-alert-button"
        )
        self.assertEqual(len(edit_buttons), 1)
        edit_button = edit_buttons[0]
        edit_button.click()
        WebDriverWait(self.selenium, 3)

        # Edit alert name
        name_field = self.selenium.find_element_by_id("id_name")
        name_field.clear()
        name_field.send_keys("Edited alert name")

        # Edit selected species (initially: no selection -> all species)
        species_select = Select(self.selenium.find_element_by_id("id_species"))
        species_select.select_by_visible_text("Orconectes virilis")

        # Edit selected datasets (initially: no selection -> all datasets)
        datasets_select = Select(self.selenium.find_element_by_id("id_datasets"))
        datasets_select.select_by_visible_text("Test dataset #2")

        # Change test alert frequency to "weekly"
        frequency_select = Select(
            self.selenium.find_element_by_id("id_email_notifications_frequency")
        )
        frequency_select.select_by_visible_text("Weekly")

        # Click the save button, gets redirected to the alerts details page
        save_button = self.selenium.find_element_by_id("pterois-alert-save-btn")
        save_button.click()

        wait = WebDriverWait(self.selenium, 3)
        # The page title contains the updated alert name
        wait.until(EC.title_contains("Alert Edited alert name details"))

        # Check the values are actually updated
        title = self.selenium.find_element_by_class_name("pterois-alert-title")
        self.assertEqual(title.text, "Edited alert name")

        species_list = self.selenium.find_element_by_id("pterois-alert-species-list")
        self.assertEqual(species_list.text, "Species: Orconectes virilis")

        datasets_list = self.selenium.find_element_by_id("pterois-alert-datasets-list")
        self.assertEqual(datasets_list.text, "Datasets: Test dataset #2")

    def test_alert_delete_scenario(self):
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        navbar.find_element_by_link_text("My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single delete form with a button (only one alert)
        delete_buttons = self.selenium.find_elements_by_class_name(
            "pterois-delete-alert-button"
        )
        self.assertEqual(len(delete_buttons), 1)
        delete_button = delete_buttons[0]

        # Action 2: click the delete button, then cancel
        delete_button.click()
        WebDriverWait(self.selenium, 3)

        modal = self.selenium.find_element_by_class_name("modal")
        modal_title = modal.find_element_by_class_name("modal-title")
        self.assertEqual(modal_title.text, "Are you sure?")
        # Is the modal visible?
        self.assertIn("show", modal.get_attribute("class"))

        # Let's cancel the action
        cancel_button = modal.find_element_by_id("modal-button-no")
        cancel_button.click()

        # The modal should now be closed
        self.assertNotIn("show", modal.get_attribute("class"))

        # Action 3: click the delete button again, then confirm
        # Let's open it again!
        delete_button.click()

        # Let's confirm the action
        confirm_button = modal.find_element_by_id("modal-button-yes")
        confirm_button.click()

        # Check 3: we're back on the "my alerts" page, with a success message and no remaining alerts
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("My alerts"))
        self.assertIn("Your alert has been deleted.", self.selenium.page_source)

        self.assertIn(
            "You currently don't have any configured alerts.", self.selenium.page_source
        )
        self.assertEqual(
            len(
                self.selenium.find_elements_by_class_name("pterois-delete-alert-button")
            ),
            0,
        )


class PteroisSeleniumTests(PteroisSeleniumTestsCommon):
    def test_seen_unseen_observations_table(self):
        """Dashboard page with a few seen and unseen observations: play with the status selector and check effect on the results table"""

        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Action 2: select table view
        table_tab = self.selenium.find_element_by_id("tab-table-view")
        table_tab.click()

        # Check 1: have a look at the all/seen/unseen button/counters
        observation_status_selector = self.selenium.find_element_by_id(
            "pterois-obs-status-selector"
        )
        seen_button = observation_status_selector.find_element_by_id(
            "label-btnRadioSeen"
        )
        seen_tab_counter_badge = seen_button.find_element_by_tag_name("span")
        self.assertEqual(seen_tab_counter_badge.text, "1")

        unseen_button = observation_status_selector.find_element_by_id(
            "label-btnRadioUnseen"
        )
        unseen_tab_counter_badge = unseen_button.find_element_by_tag_name("span")
        self.assertEqual(unseen_tab_counter_badge.text, "2")

        # Action 3: make sure "all" is selected
        observation_status_selector.find_element_by_id("label-btnRadioAll").click()

        # Check 2: make sure there are 3 rows in the table, but only 2 "unseen" badges
        obs_table = self.selenium.find_element_by_id("pterois-observations-table")
        obs_table_body = obs_table.find_element_by_tag_name("tbody")
        result_rows = obs_table_body.find_elements_by_tag_name("tr")
        self.assertEqual(len(result_rows), 3)  # 3 result rows
        unseen_badges = obs_table_body.find_elements_by_class_name(
            "pterois-unseen-badge"
        )
        self.assertEqual(len(unseen_badges), 2)

        # Action 4: select "seen"
        observation_status_selector.find_element_by_id("label-btnRadioSeen").click()
        time.sleep(1)

        # Check 3: only 1 result row, no "unseen" badge
        obs_table = self.selenium.find_element_by_id("pterois-observations-table")
        obs_table_body = obs_table.find_element_by_tag_name("tbody")
        result_rows = obs_table_body.find_elements_by_tag_name("tr")
        self.assertEqual(len(result_rows), 1)
        unseen_badges = obs_table_body.find_elements_by_class_name(
            "pterois-unseen-badge"
        )
        self.assertEqual(len(unseen_badges), 0)

        # Action 5: select "unseen"
        observation_status_selector.find_element_by_id("label-btnRadioUnseen").click()
        time.sleep(1)

        # Check 4: 2 results row, both with "unseen" badge
        obs_table = self.selenium.find_element_by_id("pterois-observations-table")
        obs_table_body = obs_table.find_element_by_tag_name("tbody")
        result_rows = obs_table_body.find_elements_by_tag_name("tr")
        self.assertEqual(len(result_rows), 2)
        unseen_badges = obs_table_body.find_elements_by_class_name(
            "pterois-unseen-badge"
        )
        self.assertEqual(len(unseen_badges), 2)

    def test_title_in_index_page(self):
        self.selenium.get(self.live_server_url)
        self.assertIn("LIFE RIPARIAS early alert", self.selenium.page_source)

    def test_normal_user_has_no_admin_access(self):
        # Sign in as a normal user
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 5)

        # There's no "Admin panel" link
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        navbar.find_element_by_link_text("testuser").click()
        with self.assertRaises(NoSuchElementException):
            navbar.find_element_by_link_text("Admin panel")

        # Trying to access the "/admin" directly is not possible neither
        self.selenium.get(self.live_server_url + "/admin")
        self.assertIn("admin/login", self.selenium.current_url)
        msg = "You are authenticated as testuser, but are not authorized to access this page. Would you like to login to a different account?"
        self.assertIn(msg, self.selenium.page_source)

    def test_superuser_has_admin_access(self):
        # sign in as a superuser
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("adminuser")
        password_field.send_keys("67890")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 5)

        # There's an "Admin panel" link
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        navbar.find_element_by_link_text(
            "adminuser"
        ).click()  # We need to open the menu first
        admin_link = navbar.find_element_by_link_text("Admin panel")
        admin_link.click()
        WebDriverWait(self.selenium, 5)

        self.assertTrue(self.selenium.current_url.endswith("/admin/"))
        self.assertEqual(self.selenium.title, "Site administration | Django site admin")

    def test_signin_signout_scenario(self):
        # We are initially not logged in and can see a "sign in" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signin_link = navbar.find_element_by_link_text("Sign in")

        # Let's click on it
        signin_link.click()

        # We are redirected to a "Sign in" page
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # We've never submitted the form, so we shouldn't have any error message
        with self.assertRaises(NoSuchElementException):
            self.selenium.find_element_by_id("pterois-invalid-credentials-message")

        # There are required username and password fields
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        self.assertEqual(username_field.get_attribute("required"), "true")
        self.assertEqual(password_field.get_attribute("required"), "true")

        # There is also a link to find a lost password on this page
        self.selenium.find_element_by_link_text("Lost password?")

        # Trying to sign in with incorrect credentials
        username_field.clear()
        password_field.clear()
        username_field.send_keys("aaa")
        password_field.send_keys("bbb")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()

        # We're still on the same page, with an error message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element_by_id(
            "pterois-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )

        # Trying with a correct username but wrong password, we should be denied too
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("wrong_password")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element_by_id(
            "pterois-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )

        # Trying with correct credentials, we should be redirected to home page and properly logged
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        logged_as_testuser = navbar.find_element_by_link_text("testuser")

        # We can click "logged as testuser" and get a menu with an option to sign out
        logged_as_testuser.click()
        signout_link = self.selenium.find_element_by_link_text("Sign out")

        # We can click the signout link
        signout_link.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we're still on the home page
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")

        # There's no more "Logged as testuser" message
        with self.assertRaises(NoSuchElementException):
            navbar.find_element_by_link_text("Logged as testuser")
        # There's a sign inlink again
        navbar.find_element_by_link_text("Sign in")

    def test_signup_scenario_existing_username(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        # We are initially not logged in and can see a "sign in" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signup_link = navbar.find_element_by_link_text("Sign up")

        # Let's click on it
        signup_link.click()

        # We are redirected to a "Sign up" page
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element_by_id("id_username")
        email_field = self.selenium.find_element_by_id("id_email")
        password1_field = self.selenium.find_element_by_id("id_password1")
        password2_field = self.selenium.find_element_by_id("id_password2")
        signup_button = self.selenium.find_element_by_id("pterois-signup-button")

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

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signup_link = navbar.find_element_by_link_text("Sign up")

        # Let's click on it
        signup_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Get the elems
        username_field = self.selenium.find_element_by_id("id_username")
        first_name_field = self.selenium.find_element_by_id("id_first_name")
        last_name_field = self.selenium.find_element_by_id("id_last_name")
        email_field = self.selenium.find_element_by_id("id_email")
        password1_field = self.selenium.find_element_by_id("id_password1")
        password2_field = self.selenium.find_element_by_id("id_password2")
        signup_button = self.selenium.find_element_by_id("pterois-signup-button")

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

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signup_link = navbar.find_element_by_link_text("Sign up")

        # Let's click on it
        signup_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element_by_id("id_username")
        email_field = self.selenium.find_element_by_id("id_email")
        password1_field = self.selenium.find_element_by_id("id_password1")
        password2_field = self.selenium.find_element_by_id("id_password2")
        signup_button = self.selenium.find_element_by_id("pterois-signup-button")

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

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signup_link = navbar.find_element_by_link_text("Sign up")

        # Let's click on it
        signup_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element_by_id("id_username")
        email_field = self.selenium.find_element_by_id("id_email")
        password1_field = self.selenium.find_element_by_id("id_password1")
        password2_field = self.selenium.find_element_by_id("id_password2")
        signup_button = self.selenium.find_element_by_id("pterois-signup-button")
        first_name_field = self.selenium.find_element_by_id("id_first_name")
        last_name_field = self.selenium.find_element_by_id("id_last_name")

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

        # We are redirected on the same page
        wait.until(EC.title_contains("Home"))

        # We appear logged
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        logged_as_peterpan = navbar.find_element_by_link_text("peterpan")

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

        # We can sign out and sign in again with the chosen credentials
        logged_as_peterpan.click()
        signout_link = self.selenium.find_element_by_link_text("Sign out")

        # We can click the sign-out link
        signout_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")

        # There's a "sign in" link again
        signin_link = navbar.find_element_by_link_text("Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("peterpan")
        password_field.send_keys("kjdshfjksd678@")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        navbar.find_element_by_link_text("peterpan")

    def test_signup_too_common_password(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signup_link = navbar.find_element_by_link_text("Sign up")

        # Let's click on it
        signup_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign up"))

        # Fill in the mandatory fields
        username_field = self.selenium.find_element_by_id("id_username")
        email_field = self.selenium.find_element_by_id("id_email")
        password1_field = self.selenium.find_element_by_id("id_password1")
        password2_field = self.selenium.find_element_by_id("id_password2")
        signup_button = self.selenium.find_element_by_id("pterois-signup-button")

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
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signin_link = navbar.find_element_by_link_text("Sign in")

        # We can follow it to the sign in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        menu = navbar.find_element_by_link_text("testuser")
        menu.click()

        # We can navigate to the "profile" page
        my_profile = navbar.find_element_by_link_text("My profile")
        my_profile.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("My profile"))

        # Basic checks on the form fields
        username_field = self.selenium.find_element_by_id("id_username")
        self.assertEqual(username_field.get_attribute("disabled"), "true")
        self.assertEqual(username_field.get_attribute("value"), "testuser")
        first_name_field = self.selenium.find_element_by_id("id_first_name")
        self.assertEqual(first_name_field.get_attribute("value"), "John")
        last_name_field = self.selenium.find_element_by_id("id_last_name")
        self.assertEqual(last_name_field.get_attribute("value"), "Frusciante")
        email_field = self.selenium.find_element_by_id("id_email")
        self.assertEqual(email_field.get_attribute("value"), "frusciante@gmail.com")

        # Let's update the values
        first_name_field.clear()
        first_name_field.send_keys("Amanda")
        last_name_field.clear()
        last_name_field.send_keys("Palmer")
        email_field.clear()
        email_field.send_keys("palmer@gmail.com")
        save_button = self.selenium.find_element_by_id("pterois-profile-save-button")
        save_button.click()

        # Check for the success message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))
        self.assertIn(
            "Your profile was successfully updated.", self.selenium.page_source
        )

        # Go to the profile again to check the values were updated
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        menu = navbar.find_element_by_link_text("testuser")
        menu.click()
        my_profile = navbar.find_element_by_link_text("My profile")
        my_profile.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("My profile"))

        username_field = self.selenium.find_element_by_id("id_username")
        self.assertEqual(username_field.get_attribute("value"), "testuser")
        first_name_field = self.selenium.find_element_by_id("id_first_name")
        self.assertEqual(first_name_field.get_attribute("value"), "Amanda")
        last_name_field = self.selenium.find_element_by_id("id_last_name")
        self.assertEqual(last_name_field.get_attribute("value"), "Palmer")
        email_field = self.selenium.find_element_by_id("id_email")
        self.assertEqual(email_field.get_attribute("value"), "palmer@gmail.com")

    def test_no_profile_page_if_not_logged(self):
        """We try to access the profile page directly from the URL, without being signed in"""
        self.selenium.get(self.live_server_url + "/profile")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(
            EC.url_contains("/accounts/signin/?next=/profile")
        )  # We are redirected to the login page

    def test_lost_password_scenario(self):
        # In test_signin_signout_scenario, we make sure there is a link on login page to get a password back
        # In this test we check that feature works as expected
        # TODO: implement
        pass

    def test_delete_account_scenario(self):
        """A user wants to delete his account, and need to confirm the action"""
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        signin_link = navbar.find_element_by_link_text("Sign in")

        # We can follow it to the sign in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 3)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        menu = navbar.find_element_by_link_text("testuser")
        menu.click()

        # We can navigate to the "profile" page
        my_profile = navbar.find_element_by_link_text("My profile")
        my_profile.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("My profile"))

        delete_account_button = self.selenium.find_element_by_id(
            "pterois-profile-delete-account-button"
        )
        delete_account_button.click()
        modal = self.selenium.find_element_by_class_name("modal")
        modal_title = modal.find_element_by_class_name("modal-title")
        self.assertEqual(modal_title.text, "Are you sure?")
        # Is the modal visible?
        self.assertIn("show", modal.get_attribute("class"))

        # Let's cancel the action
        cancel_button = modal.find_element_by_id("modal-button-no")
        cancel_button.click()

        # The modal should now be closed
        self.assertNotIn("show", modal.get_attribute("class"))

        # Let's open it again!
        delete_account_button.click()

        # Let's confirm the action
        confirm_button = modal.find_element_by_id("modal-button-yes")
        confirm_button.click()

        # We should now be redirected to the home page, with a proper message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))
        self.assertIn("Your account has been deleted.", self.selenium.page_source)

        # We should be visibly logged out
        navbar = self.selenium.find_element_by_id("pterois-main-navbar")
        # There's no more "Logged as testuser" message
        with self.assertRaises(NoSuchElementException):
            navbar.find_element_by_link_text("Logged as testuser")
        # There's a sign in link again
        signin_link = navbar.find_element_by_link_text("Sign in")

        # Let's try to sign in again...
        signin_link.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element_by_id("pterois-signin-button")
        signin_button.click()

        # This is not possible anymore...
        # ... so we're still on the same page, with an error message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))
        error_message = self.selenium.find_element_by_id(
            "pterois-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )
