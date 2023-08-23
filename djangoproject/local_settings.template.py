import os
from typing import Any

from .settings import *

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
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
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
    }
}

# Redis configuration for django-rq
RQ_QUEUES = {
    "default": {
        "HOST": os.getenv("REDIS_HOST"),
        "PORT": os.getenv("REDIS_PORT"),
        "DB": 0,
        "PASSWORD": os.getenv("REDIS_PASSWORD"),
        "DEFAULT_TIMEOUT": 360,
    },
}

# Email-sending configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
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


# You must provide a function to build a GBIF download predicate, similar to the example below.
# The "TAXON_KEY in" section should stay intact, so the species are selected based on what's in the
# local database.
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
