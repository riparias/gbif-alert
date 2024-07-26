import datetime
import re
import time

from django.conf import settings
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
)
from dashboard.views.helpers import create_or_refresh_all_materialized_views


def _get_webdriver() -> WebDriver:
    # Selenium setup
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
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
    },
    DEBUG=True,
)
class SeleniumTestsCommon(StaticLiveServerTestCase):
    """Common test data and Selenium-related plumbing"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = _get_webdriver()

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

        self.obs_1 = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=self.first_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=self.first_dataset,
            location=Point(5.09513, 50.48941, srid=4326),
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


class SeleniumAlertTests(SeleniumTestsCommon):
    """Integration tests for the alert-related features"""

    def test_alert_edit_cancel_scenario(self):
        """The user go to the edit alert page, but change its mind and cancel"""
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single edit alert button (only one alert)
        edit_buttons = self.selenium.find_elements(
            By.CLASS_NAME, "gbif-alert-edit-alert-button"
        )
        self.assertEqual(len(edit_buttons), 1)
        edit_button = edit_buttons[0]
        edit_button.click()
        WebDriverWait(self.selenium, 3)

        # Om the edit alert page, let's click the cancel button and make sure we go back to the alerts list
        cancel_button = self.selenium.find_element(
            By.LINK_TEXT, "Go back to alerts list"
        )
        self.selenium.execute_script("arguments[0].scrollIntoView();", cancel_button)
        self.selenium.execute_script("arguments[0].click();", cancel_button)

        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("My alerts"))

    def test_alert_edit_validation_errors_scenario(self):
        pass
        # TODO: implement this test

    def test_alert_edit_initial_values(self):
        """The user go to the edit alert page, and the initial values are correct for the alert"""
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single edit alert button (only one alert)
        edit_buttons = self.selenium.find_elements(
            By.CLASS_NAME, "gbif-alert-edit-alert-button"
        )
        self.assertEqual(len(edit_buttons), 1)
        edit_button = edit_buttons[0]
        edit_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 3: the initial values are correct
        time.sleep(1)

        #  3.1 - the name field is correct
        name_field = self.selenium.find_element(By.ID, "alertName")
        self.assertEqual(name_field.get_attribute("value"), "Test alert")

        #  3.2 - the species selection is correct
        species_section = self.selenium.find_element(
            By.ID, "gbif-alert-alert-species-selection"
        )
        first_species_checkbox = species_section.find_element(
            By.CSS_SELECTOR, f"input[type='checkbox'][value='{self.first_species.pk}']"
        )
        second_species_checkbox = species_section.find_element(
            By.CSS_SELECTOR, f"input[type='checkbox'][value='{self.second_species.pk}']"
        )
        self.assertTrue(first_species_checkbox.is_selected())
        self.assertFalse(second_species_checkbox.is_selected())

        #  3.3 - the datasets selection is correct
        datasets_section = self.selenium.find_element(
            By.ID, "gbif-alert-alert-datasets-selection"
        )

        for value in [self.first_dataset.pk, self.second_dataset.pk]:
            dataset_checkbox = datasets_section.find_element(
                By.CSS_SELECTOR, f"input[type='checkbox'][value='{value}']"
            )
            self.assertFalse(dataset_checkbox.is_selected())

        # 3.4 - no areas in test data, so list is empty, and we have nothing to test

        # 3.5 - the email frequency field is correct
        frequency_select = Select(
            self.selenium.find_element(By.ID, "gbif-alert-alert-frequency-select")
        )

        self.assertEqual(frequency_select.first_selected_option.text, "Daily")

    def test_alert_edit_scenario(self):
        """The user go to the edit alert page, make edits and save them"""
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")

        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single edit alert button (only one alert)
        edit_buttons = self.selenium.find_elements(
            By.CLASS_NAME, "gbif-alert-edit-alert-button"
        )
        self.assertEqual(len(edit_buttons), 1)
        edit_button = edit_buttons[0]
        edit_button.click()
        WebDriverWait(self.selenium, 3)

        # Edit alert name
        name_field = self.selenium.find_element(By.ID, "alertName")
        # Sometimes, clear isn't enough...
        name_field.send_keys(Keys.CONTROL, "a")
        name_field.send_keys(Keys.COMMAND, "a")  # For Mac users
        name_field.send_keys(Keys.DELETE)
        name_field.clear()

        name_field.send_keys("Edited alert name")

        # Edit selected species (initially: one species -> all species)
        species_section = self.selenium.find_element(
            By.ID, "gbif-alert-alert-species-selection"
        )
        species_section.find_element(
            By.CSS_SELECTOR, f"input[type='checkbox'][value='{self.second_species.pk}']"
        ).click()  # Select also the second species

        # Edit selected datasets (initially: no selection -> all datasets)
        datasets_section = self.selenium.find_element(
            By.ID, "gbif-alert-alert-datasets-selection"
        )

        for value in [self.first_dataset.pk, self.second_dataset.pk]:
            elem = datasets_section.find_element(
                By.CSS_SELECTOR, f"input[type='checkbox'][value='{value}']"
            )
            self.selenium.execute_script("arguments[0].scrollIntoView();", elem)
            self.selenium.execute_script("arguments[0].click();", elem)

        # Change test alert frequency to "weekly" (initially daily)
        frequency_select = Select(
            self.selenium.find_element(By.ID, "gbif-alert-alert-frequency-select")
        )
        frequency_select.select_by_visible_text("Weekly")

        # Click the save button

        save_button = self.selenium.find_element(By.ID, "gbif-alert-alert-save-btn")
        self.selenium.execute_script("arguments[0].scrollIntoView();", save_button)
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.element_to_be_clickable(save_button))
        time.sleep(1)
        save_button.click()

        # We get a success message
        wait = WebDriverWait(self.selenium, 3)
        wait.until(
            EC.presence_of_element_located(
                (By.ID, "gbif-alert-alert-successfully-saved")
            )
        )

        # We now have a button to see the details of the alert, let's click it
        alert_page_button = self.selenium.find_element(
            By.LINK_TEXT, "View alert observations"
        )
        alert_page_button.click()

        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Alert details"))

        alert_title = self.selenium.find_element(
            By.CLASS_NAME, "gbif-alert-alert-title"
        )
        self.assertEqual(alert_title.text, "Edited alert name")

        species_list_text = self.selenium.find_element(
            By.ID, "gbif-alert-alert-species-list"
        ).text
        self.assertIn("Orconectes virilis", species_list_text)
        self.assertIn("Procambarus fallax", species_list_text)

        datasets_list_text = self.selenium.find_element(
            By.ID, "gbif-alert-alert-datasets-list"
        ).text
        self.assertIn("Test dataset", datasets_list_text)
        self.assertIn("Test dataset #2", datasets_list_text)

        # Check that the alert frequency is weekly
        frequency_text = self.selenium.find_element(
            By.ID, "gbif-alert-alert-frequency"
        ).text
        self.assertIn("Weekly", frequency_text)

    def test_alert_delete_scenario(self):
        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Check 1: There a "my alerts" link we can follow
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "My alerts").click()
        WebDriverWait(self.selenium, 3)

        # Check 2: on the page, there's a single delete form with a button (only one alert)
        delete_buttons = self.selenium.find_elements(
            By.CLASS_NAME, "gbif-alert-delete-alert-button"
        )
        self.assertEqual(len(delete_buttons), 1)
        delete_button = delete_buttons[0]

        # Action 2: click the delete button, then cancel
        delete_button.click()
        WebDriverWait(self.selenium, 3)

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

        # Action 3: click the delete button again, then confirm
        # Let's open it again!
        delete_button.click()

        # Let's confirm the action
        confirm_button = modal.find_element(By.ID, "modal-button-yes")
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
                self.selenium.find_elements(
                    By.CLASS_NAME, "gbif-alert-delete-alert-button"
                )
            ),
            0,
        )


class SeleniumTests(SeleniumTestsCommon):
    def test_seen_unseen_observations_table(self):
        """Dashboard page with a few seen and unseen observations: play with the status selector and check effect on the results table"""

        # Action 1: login
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 3)

        # Action 2: select table view
        table_tab = self.selenium.find_element(By.ID, "tab-table-view")
        table_tab.click()

        # Check 1: have a look at the all/seen/unseen button/counters
        observation_status_selector = self.selenium.find_element(
            By.ID, "gbif-alert-obs-status-selector"
        )
        seen_button = observation_status_selector.find_element(
            By.ID, "label-btnRadioSeen"
        )
        seen_tab_counter_badge = seen_button.find_element(By.TAG_NAME, "span")
        self.assertEqual(seen_tab_counter_badge.text, "1")

        unseen_button = observation_status_selector.find_element(
            By.ID, "label-btnRadioUnseen"
        )
        unseen_tab_counter_badge = unseen_button.find_element(By.TAG_NAME, "span")
        self.assertEqual(unseen_tab_counter_badge.text, "2")

        # Action 3: make sure "all" is selected
        observation_status_selector.find_element(By.ID, "label-btnRadioAll").click()

        # Check 2: make sure there are 3 rows in the table, but only 2 "unseen" badges
        obs_table = self.selenium.find_element(By.ID, "gbif-alert-observations-table")
        obs_table_body = obs_table.find_element(By.TAG_NAME, "tbody")
        result_rows = obs_table_body.find_elements(By.TAG_NAME, "tr")
        self.assertEqual(len(result_rows), 3)  # 3 result rows
        unseen_badges = obs_table_body.find_elements(
            By.CLASS_NAME, "gbif-alert-unseen-badge"
        )
        self.assertEqual(len(unseen_badges), 2)

        # Action 4: select "seen"
        observation_status_selector.find_element(By.ID, "label-btnRadioSeen").click()
        time.sleep(1)

        # Check 3: only 1 result row, no "unseen" badge
        obs_table = self.selenium.find_element(By.ID, "gbif-alert-observations-table")
        obs_table_body = obs_table.find_element(By.TAG_NAME, "tbody")
        result_rows = obs_table_body.find_elements(By.TAG_NAME, "tr")
        self.assertEqual(len(result_rows), 1)
        unseen_badges = obs_table_body.find_elements(
            By.CLASS_NAME, "gbif-alert-unseen-badge"
        )
        self.assertEqual(len(unseen_badges), 0)

        # Action 5: select "unseen"
        observation_status_selector.find_element(By.ID, "label-btnRadioUnseen").click()
        time.sleep(1)

        # Check 4: 2 results row, both with "unseen" badge
        obs_table = self.selenium.find_element(By.ID, "gbif-alert-observations-table")
        obs_table_body = obs_table.find_element(By.TAG_NAME, "tbody")
        result_rows = obs_table_body.find_elements(By.TAG_NAME, "tr")
        self.assertEqual(len(result_rows), 2)
        unseen_badges = obs_table_body.find_elements(
            By.CLASS_NAME, "gbif-alert-unseen-badge"
        )
        self.assertEqual(len(unseen_badges), 2)

        # Let's test the mark as unseen button
        # Re-select seen
        observation_status_selector.find_element(By.ID, "label-btnRadioSeen").click()
        time.sleep(1)
        # Go to the observation page
        result_rows[0].find_element(By.TAG_NAME, "a").click()
        time.sleep(1)
        # Click the "mark as unseen" button
        WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='Mark this observation as unseen']")
            )
        ).click()

        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))

        # The unseen counter should be at 3 and the seen at 0 (invisible)
        observation_status_selector = self.selenium.find_element(
            By.ID, "gbif-alert-obs-status-selector"
        )
        seen_button = observation_status_selector.find_element(
            By.ID, "label-btnRadioSeen"
        )

        unseen_button = observation_status_selector.find_element(
            By.ID, "label-btnRadioUnseen"
        )
        unseen_tab_counter_badge = unseen_button.find_element(By.TAG_NAME, "span")
        self.assertEqual(unseen_tab_counter_badge.text, "3")

    def test_title_in_index_page(self):
        self.selenium.get(self.live_server_url)
        self.assertIn("LIFE RIPARIAS early alert", self.selenium.page_source)

    def test_normal_user_has_no_admin_access(self):
        # Sign in as a normal user
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 5)

        # There's no "Admin panel" link
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "testuser").click()
        with self.assertRaises(NoSuchElementException):
            navbar.find_element(By.LINK_TEXT, "Admin panel")

        # Trying to access the "/admin" directly is not possible neither
        self.selenium.get(self.live_server_url + "/admin")
        self.assertIn("admin/login", self.selenium.current_url)
        msg = "You are authenticated as testuser, but are not authorized to access this page. Would you like to login to a different account?"
        self.assertIn(msg, self.selenium.page_source)

    def test_superuser_has_admin_access(self):
        # sign in as a superuser
        self.selenium.get(self.live_server_url + "/accounts/signin/")
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("adminuser")
        password_field.send_keys("67890")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        WebDriverWait(self.selenium, 5)

        # There's an "Admin panel" link
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(
            By.LINK_TEXT, "adminuser"
        ).click()  # We need to open the menu first
        admin_link = navbar.find_element(By.LINK_TEXT, "Admin panel")
        admin_link.click()
        WebDriverWait(self.selenium, 5)

        self.assertTrue(self.selenium.current_url.endswith("/admin/"))
        self.assertEqual(self.selenium.title, "Site administration | Django site admin")

    def test_signin_signout_scenario(self):
        # We are initially not logged in and can see a "sign in" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # Let's click on it
        signin_link.click()

        # We are redirected to a "Sign in" page
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

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        logged_as_testuser = navbar.find_element(By.LINK_TEXT, "testuser")

        # We can click "logged as testuser" and get a menu with an option to sign out
        logged_as_testuser.click()
        signout_link = self.selenium.find_element(By.LINK_TEXT, "Sign out")

        # We can click the signout link
        signout_link.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we're still on the home page
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")

        # There's no more "Logged as testuser" message
        with self.assertRaises(NoSuchElementException):
            navbar.find_element(By.LINK_TEXT, "Logged as testuser")
        # There's a sign in link again
        navbar.find_element(By.LINK_TEXT, "Sign in")

    def test_signup_scenario_existing_username(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        # We are initially not logged in and can see a "sign in" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signup_link = navbar.find_element(By.LINK_TEXT, "Sign up")

        # Let's click on it
        signup_link.click()

        # We are redirected to a "Sign up" page
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

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signup_link = navbar.find_element(By.LINK_TEXT, "Sign up")

        # Let's click on it
        signup_link.click()
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

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signup_link = navbar.find_element(By.LINK_TEXT, "Sign up")

        # Let's click on it
        signup_link.click()
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

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signup_link = navbar.find_element(By.LINK_TEXT, "Sign up")

        # Let's click on it
        signup_link.click()
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

        # We are redirected on the same page
        wait.until(EC.title_contains("Home"))

        # We appear logged
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        logged_as_peterpan = navbar.find_element(By.LINK_TEXT, "peterpan")

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
        signout_link = self.selenium.find_element(By.LINK_TEXT, "Sign out")

        # We can click the sign-out link
        signout_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")

        # There's a "sign in" link again
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("peterpan")
        password_field.send_keys("kjdshfjksd678@")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "peterpan")

        # All the existing observations are considered as seen by this new user
        existing_observations = Observation.objects.all()
        for obs in existing_observations:
            self.assertTrue(obs.already_seen_by(latest_created_user))

    def test_signup_too_common_password(self):
        User = get_user_model()
        number_users_before = User.objects.count()

        # We are initially not logged in and can see a "sign up" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signup_link = navbar.find_element(By.LINK_TEXT, "Sign up")

        # Let's click on it
        signup_link.click()
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
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 5)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        menu = navbar.find_element(By.LINK_TEXT, "testuser")
        menu.click()

        # We can navigate to the "profile" page
        my_profile = navbar.find_element(By.LINK_TEXT, "My profile")
        my_profile.click()
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

        # Let's update the values
        first_name_field.clear()
        first_name_field.send_keys("Amanda")
        last_name_field.clear()
        last_name_field.send_keys("Palmer")
        email_field.clear()
        email_field.send_keys("palmer@gmail.com")
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
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        menu = navbar.find_element(By.LINK_TEXT, "testuser")
        menu.click()
        my_profile = navbar.find_element(By.LINK_TEXT, "My profile")
        my_profile.click()
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

    def test_no_profile_page_if_not_logged(self):
        """We try to access the profile page directly from the URL, without being signed in"""
        self.selenium.get(self.live_server_url + "/profile")
        wait = WebDriverWait(self.selenium, 5)
        wait.until(
            EC.url_contains("/accounts/signin/?next=/profile")
        )  # We are redirected to the login page

    def test_lost_password_scenario_wrong_address(self):
        # In test_signin_signout_scenario(), we make sure there is a link on login page to get a password back
        # In this test we check that the feature works as expected
        # Case 1: password not linked to any account
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
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
        # In test_signin_signout_scenario(), we make sure there is a link on login page to get a password back
        # In this test we check that the feature works as expected
        # Case 2: successful password reset
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
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
        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        navbar.find_element(By.LINK_TEXT, "testuser")

    def test_change_password_scenario(self):
        """A logged user wants to change his password"""
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 3)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        menu = navbar.find_element(By.LINK_TEXT, "testuser")
        menu.click()

        # We can navigate to the "change my password" page
        my_profile = navbar.find_element(By.LINK_TEXT, "Change my password")
        my_profile.click()
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

        # We can now sign out
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        menu = navbar.find_element(By.LINK_TEXT, "testuser")
        menu.click()
        signout_link = navbar.find_element(By.LINK_TEXT, "Sign out")
        signout_link.click()

        # We can sign in again, with the new password
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")
        signin_link.click()
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
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # We can follow it to the sign-in page
        signin_link.click()
        wait = WebDriverWait(self.selenium, 3)
        wait.until(EC.title_contains("Sign in"))

        # And successfully sign in
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        signin_button = self.selenium.find_element(By.ID, "gbif-alert-signin-button")
        signin_button.click()
        wait = WebDriverWait(self.selenium, 3)

        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        menu = navbar.find_element(By.LINK_TEXT, "testuser")
        menu.click()

        # We can navigate to the "profile" page
        my_profile = navbar.find_element(By.LINK_TEXT, "My profile")
        my_profile.click()
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

        # We should be visibly logged out
        navbar = self.selenium.find_element(By.ID, "gbif-alert-main-navbar")
        # There's no more "Logged as testuser" message
        with self.assertRaises(NoSuchElementException):
            navbar.find_element(By.LINK_TEXT, "Logged as testuser")
        # There's a sign in link again
        signin_link = navbar.find_element(By.LINK_TEXT, "Sign in")

        # Let's try to sign in again...
        signin_link.click()
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
