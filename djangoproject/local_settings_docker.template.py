from typing import Any

from .local_settings_docker_base import * # type: ignore

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "<something secret here>"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # TODO: change this


# Email-sending configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "email-smtp.eu-west-1.amazonaws.com"
EMAIL_HOST_USER = "yyy"
EMAIL_HOST_PASSWORD = "xxx"
EMAIL_SUBJECT_PREFIX = "[dev-alert.riparias.be] "
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = (
    "LIFE RIPARIAS early alert <info@dev-alert.localhost>"  # Used for normal messages
)
SERVER_EMAIL = "LIFE RIPARIAS early alert <info@dev-alert.riparias.be>"  # Used to contact admins for errors, ...

# used to refer to the website in emails! Points to the site root, includes protocol, host, port... No trailing slash.
SITE_BASE_URL = "http://localhost:8001"

ADMINS = [
    ("Nicolas", "nicolas@niconoe.eu"),
]

GBIF_ALERT: dict[str, Any] = {
    "SITE_NAME": "LIFE RIPARIAS early alert - local",
    "NAVBAR_BACKGROUND_COLOR": "crimson",
    "NAVBAR_LIGHT_TEXT": True,
    "ENABLED_LANGUAGES": (
        "en",
        "fr",
        # "nl",
    ),  # Languages available in the interface. Subset of the languages in `LANGUAGES`.
    # A Gbif.org account is necessary to automatically download observations via the `import_observations` command
    "GBIF_DOWNLOAD_CONFIG": {
        "USERNAME": "aaaa",
        "PASSWORD": "bbbb",
        "COUNTRY_CODE": "BE",  # Only download observations from this country
        "MINIMUM_YEAR": 2000,  # Observations must be from this year or later
    },
    "SHOW_DEV_VERSION_WARNING": False,
    "MAIN_MAP_CONFIG": {
        "initialZoom": 8,
        "initialLat": 50.50,
        "initialLon": 4.47,
    },
    "HIDE_MY_CUSTOM_AREAS_PAGE": False,
}
