from typing import Dict, Any

from .settings import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "<something secret here>"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "github_actions",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}

RQ_QUEUES = {
    "default": {
        "HOST": "127.0.0.1",
        "PORT": 6379,
    },
}

# used to refer to the website in emails! Points to the site root, includes protocol, host, port... No trailing slash.
SITE_BASE_URL = "http://localhost"

PTEROIS: Dict[str, Any] = {
    "SITE_NAME": "LIFE RIPARIAS early alert",
    "ENABLED_LANGUAGES": (
        "en",
        "fr",
    ),  # Languages available in the interface. Subset of the languages in `LANGUAGES`.
    "GBIF_DOWNLOAD_CONFIG": {
        "USERNAME": "riparias-dev",
        "PASSWORD": "riparias-dev",
        "COUNTRY_CODE": "BE",  # Only download observations from this country
        "MINIMUM_YEAR": 2000,  # Observations must be from this year or later
    },
    "SHOW_DEV_VERSION_WARNING": False,
    "MAIN_MAP_CONFIG": {
        "initialZoom": 8,
        "initialLat": 50.50,
        "initialLon": 4.47,
    },
}

SELENIUM_CHROMEDRIVER_VERSION = "111.0.5563.19"
