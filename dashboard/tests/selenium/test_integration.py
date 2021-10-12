from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver  # type: ignore
from selenium.common.exceptions import NoSuchElementException  # type: ignore
from selenium.webdriver.support.wait import WebDriverWait  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from webdriver_manager.chrome import ChromeDriverManager  # type: ignore


class RipariasSeleniumTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Selenium setup
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--headless")
        options.add_argument("--window-size=1280,800")
        cls.selenium = webdriver.Chrome(
            ChromeDriverManager().install(), options=options
        )
        cls.selenium.implicitly_wait(5)
        # Create a test user
        User = get_user_model()
        User.objects.create_user(username="testuser", password="12345")

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def test_title_in_page(self):
        self.selenium.get(self.live_server_url)
        self.assertIn("LIFE RIPARIAS early alert", self.selenium.page_source)

    def test_login_logout_scenario(self):
        # We are initially not logged in and can see a "log in" link
        self.selenium.get(self.live_server_url)
        navbar = self.selenium.find_element_by_id("riparias-main-navbar")
        login_link = navbar.find_element_by_link_text("Log in")

        # Let's click on it
        login_link.click()

        # We are redirected to a "Log in" page
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Log in"))

        # We've never submitted the form, so we shouldn't have any error message
        with self.assertRaises(NoSuchElementException):
            self.selenium.find_element_by_id("riparias-invalid-credentials-message")

        # There are required username and password fields
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        self.assertEqual(username_field.get_attribute("required"), "true")
        self.assertEqual(password_field.get_attribute("required"), "true")

        # There is also a link to find a lost password on this page
        self.selenium.find_element_by_link_text("Lost password?")

        # Trying to log in with incorrect credentials
        username_field.clear()
        password_field.clear()
        username_field.send_keys("aaa")
        password_field.send_keys("bbb")
        login_button = self.selenium.find_element_by_id("riparias-login-button")
        login_button.click()

        # We're still on the same page, with an error message
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Log in"))
        error_message = self.selenium.find_element_by_id(
            "riparias-invalid-credentials-message"
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
        login_button = self.selenium.find_element_by_id("riparias-login-button")
        login_button.click()
        wait = WebDriverWait(self.selenium, 5)
        wait.until(EC.title_contains("Log in"))
        error_message = self.selenium.find_element_by_id(
            "riparias-invalid-credentials-message"
        )
        self.assertEqual(
            error_message.text,
            "Your username and password didn't match. Please try again.",
        )

        # Trying with correct credentials, we should be redirected to home page and properly
        # logged
        username_field = self.selenium.find_element_by_id("id_username")
        password_field = self.selenium.find_element_by_id("id_password")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("testuser")
        password_field.send_keys("12345")
        login_button = self.selenium.find_element_by_id("riparias-login-button")
        login_button.click()
        wait = WebDriverWait(self.selenium, 5)
        # Now, we should be redirected to the home page, and see the username in the navbar
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("riparias-main-navbar")
        logged_as_testuser = navbar.find_element_by_link_text("Logged as testuser")
        # We can click "logged as testuser" and get a menu with an option to log out
        logged_as_testuser.click()
        logout_link = self.selenium.find_element_by_link_text("Log out")
        # We can click the logout link
        logout_link.click()
        wait = WebDriverWait(self.selenium, 5)
        # Now, we're still on the home page
        wait.until(EC.title_contains("Home"))
        navbar = self.selenium.find_element_by_id("riparias-main-navbar")
        # There's no more "Logged as testuser" message
        with self.assertRaises(NoSuchElementException):
            navbar.find_element_by_link_text("Logged as testuser")
        # There's a log in link again
        navbar.find_element_by_link_text("Log in")

    def test_lost_password_scenario(self):
        # In test_login_logout_scenario, we make sure there is a link on login page to get a password back
        # In this test we check that feature works as expected
        # TODO: implement
        pass
