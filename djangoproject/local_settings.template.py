from typing import Any

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
        "NAME": "pterois",
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
EMAIL_SUBJECT_PREFIX = "[pterois-instance-url] "
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = (
    "Pterois instance name <info@pterois.xyz>"  # Used for normal messages
)
SERVER_EMAIL = "Pterois instance name <info@pterois.xyz>"  # Used to contact admins for errors, ...

# used to refer to the website in emails! Points to the site root, includes protocol, host, port... No trailing slash.
SITE_BASE_URL = "http://pterois.xyz"

ADMINS = [
    ("your name", "your@email.xyz"),
]

PTEROIS: dict[str, Any] = {
    "SITE_NAME": "Pterois test instance",
    "ENABLED_LANGUAGES": (
        "en",
        "fr",
    ),  # Languages available in the interface. Subset of the languages in `LANGUAGES`.
    "GBIF_DOWNLOAD_CONFIG": {
        # A GBIF.org account is required to download data from GBIF.org, please create one then enter your credentials here.
        "USERNAME": "pterois-gbif-username",
        "PASSWORD": "pterois-gbif-password",
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
