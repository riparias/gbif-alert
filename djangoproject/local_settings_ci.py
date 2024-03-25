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
    "SITE_NAME": "LIFE RIPARIAS early alert",
    "NAVBAR_BACKGROUND_COLOR": "#00a58d",
    "NAVBAR_LIGHT_TEXT": True,
    "ENABLED_LANGUAGES": (
        "en",
        "fr",
    ),  # Languages available in the interface. Subset of the languages in `LANGUAGES`.
    "GBIF_DOWNLOAD_CONFIG": {
        "USERNAME": "riparias-dev",
        "PASSWORD": "riparias-dev",
        "PREDICATE_BUILDER": build_gbif_download_predicate,
    },
    "MAIN_MAP_CONFIG": {
        "initialZoom": 8,
        "initialLat": 50.50,
        "initialLon": 4.47,
    },
}
