from typing import Any

from .settings import *

from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)  # loads the configs from .env
# From now on, you can use os.getenv("SOME_KEY_FROM_ENV_FILE") to get access to a secret key

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "gbif-alert",
    }
}

# Redis configuration for django-rq
RQ_QUEUES = {
    "default": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        "PASSWORD": "some-password",
        "DEFAULT_TIMEOUT": 360,
    },
}

# Email-sending configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "email-smtp.eu-west-1.amazonaws.com"
EMAIL_HOST_USER = "yyy"
EMAIL_HOST_PASSWORD = "xxx"
EMAIL_SUBJECT_PREFIX = "[gbif-alert-instance-url] "
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = (
    "GBIF alert instance name <info@gbif-alert.xyz>"  # Used for normal messages
)
SERVER_EMAIL = "GBIF alert instance name <info@gbif-alert.xyz>"  # Used to contact admins for errors, ...

# used to refer to the website in emails! Points to the site root, includes protocol, host, port... No trailing slash.
SITE_BASE_URL = "http://gbif-alert.xyz"

ADMINS = [
    ("your name", "your@email.xyz"),
]


def build_gbif_download_predicate(species_list: "QuerySet[Species]"):  # type: ignore
    """
    Build a GBIF.org download predicate for Belgian observations, after 2000.

    Species list is taken from the GBIF Alert database.
    """
    return {
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "COUNTRY", "value": "BE"},
                {
                    "type": "in",
                    "key": "TAXON_KEY",
                    "values": [f"{s.gbif_taxon_key}" for s in species_list],
                },
                {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "present"},
                {
                    "type": "greaterThanOrEquals",
                    "key": "YEAR",
                    "value": 2000,
                },
            ],
        }
    }


GBIF_ALERT: dict[str, Any] = {
    "SITE_NAME": "GBIF Alert test instance",  # Name of the website, appears in various places (page titles, emails, ...)
    "NAVBAR_BACKGROUND_COLOR": "red",
    "NAVBAR_LIGHT_TEXT": True,  # Whether the text in the navbar should be light or dark
    "ENABLED_LANGUAGES": (  # Languages available in the interface. Subset of the languages in `LANGUAGES`.
        "en",
        "fr",
    ),
    # A valid Gbif.org account is necessary to automatically download observations via the `import_observations` command
    # We recommend creating a dedicated account for this purpose, not your personal one.
    "GBIF_DOWNLOAD_CONFIG": {
        "USERNAME": os.getenv("GBIF_USERNAME"),
        "PASSWORD": os.getenv("GBIF_PASSWORD"),
        "PREDICATE_BUILDER": build_gbif_download_predicate,
    },
    # Deprecated: this settings will disappear soon (https://github.com/riparias/gbif-alert/issues/250), keep it to False
    "SHOW_DEV_VERSION_WARNING": False,
    # initial location of the map on the index page
    "MAIN_MAP_CONFIG": {
        "initialZoom": 8,
        "initialLat": 50.50,
        "initialLon": 4.47,
    },
    # The "my custom areas" page is a page where users can create their own areas of interest.
    # It is currently in progress (lacks documentation, UI is poor, missing translations, ...), so we offer the a feature flag to hide it.
    "HIDE_MY_CUSTOM_AREAS_PAGE": False,
}
