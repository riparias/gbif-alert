"""
Django settings for djangoproject project.

Generated by 'django-admin startproject' using Django 3.2.6.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import os
from pathlib import Path

import fsutil

# Build paths inside the project like this: BASE_DIR / 'subdir'.

from django.contrib import messages
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent
THIS_DIR = os.path.dirname(__file__)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

ALLOWED_HOSTS: list[str] = []


# Application definition

INSTALLED_APPS = [
    # Django
    "modeltranslation",  # Must be placed before the admin app: https://github.com/deschler/django-modeltranslation/issues/408
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.humanize",
    # Third-party
    "maintenance_mode",
    "crispy_forms",
    "crispy_bootstrap5",
    "import_export",
    "corsheaders",
    "markdownx",
    "django_rq",
    "taggit",
    "gisserver",
    # Beware, there's also "modeltranslation", but it had to be placed before the admin app
    # Local/custom
    "dashboard",
    "page_fragments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "maintenance_mode.middleware.MaintenanceModeMiddleware",
]

ROOT_URLCONF = "djangoproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.context_processors.latest_data_import_processor",
                "dashboard.context_processors.gbif_alert_settings",
                "dashboard.context_processors.gbif_alert_various",
            ],
        },
    },
]

WSGI_APPLICATION = "djangoproject.wsgi.application"


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

# Beware: when adding a new language, you also need to run `python manage.py makemigrations` (it is referenced from the user profile model)
LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("nl", _("Dutch")),
]

TIME_ZONE = "Europe/Brussels"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"


STATICFILES_DIRS: list[str] = [os.path.join(BASE_DIR, "static_global")]
STATIC_ROOT = os.path.join(BASE_DIR, "static")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}


# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "dashboard.User"

LOGIN_URL = "signin"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

MESSAGE_TAGS = {
    messages.ERROR: "danger",  # To match Bootstrap's classes
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_METHODS = [
    "GET"
]  # Probably needed, but just to be on the safe side. See https://github.com/riparias/gbif-alert/issues/100

PAGE_FRAGMENTS_FALLBACK_LANGUAGE = "en"

RQ_SHOW_ADMIN_LINK = True

# We have to explicitly set the various maintenance mode default settings because of https://github.com/fabiocaccamo/django-maintenance-mode/issues/59
MAINTENANCE_MODE = None
MAINTENANCE_MODE_STATE_BACKEND = "maintenance_mode.backends.LocalFileBackend"
MAINTENANCE_MODE_STATE_FILE_NAME = "maintenance_mode_state.txt"
MAINTENANCE_MODE_STATE_FILE_PATH = fsutil.join_path(
    THIS_DIR, MAINTENANCE_MODE_STATE_FILE_NAME
)
MAINTENANCE_MODE_IGNORE_ADMIN_SITE = False
MAINTENANCE_MODE_IGNORE_ANONYMOUS_USER = False
MAINTENANCE_MODE_IGNORE_AUTHENTICATED_USER = False
MAINTENANCE_MODE_IGNORE_STAFF = False
MAINTENANCE_MODE_IGNORE_SUPERUSER = False
MAINTENANCE_MODE_IGNORE_IP_ADDRESSES = ()
MAINTENANCE_MODE_GET_CLIENT_IP_ADDRESS = None
MAINTENANCE_MODE_IGNORE_URLS = ()
MAINTENANCE_MODE_IGNORE_TESTS = False
MAINTENANCE_MODE_REDIRECT_URL = None
MAINTENANCE_MODE_TEMPLATE = "dashboard/503.html"
MAINTENANCE_MODE_GET_CONTEXT = None
MAINTENANCE_MODE_STATUS_CODE = 503
MAINTENANCE_MODE_RETRY_AFTER = 3600
MAINTENANCE_MODE_LOGOUT_AUTHENTICATED_USER = False
MAINTENANCE_MODE_RESPONSE_TYPE = "html"

# Logging: unfortunately for us, I am not able to override the default logging config as suggested in Django's documentation (changes are ignored)
# This is similar to https://stackoverflow.com/questions/62334688/django-logger-not-logging-but-all-other-loggers-work
# I therefore copy-pasted the default config from Django's source code and modified it to my needs.
# Currently applied changes:
# - Added a filter to ignore 503 errors when in maintenance mode
# - "include_html": True for the emails to admins in case of errors
LOGGING_CONFIG = None
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "require_not_maintenance_mode_503": {
            "()": "maintenance_mode.logging.RequireNotMaintenanceMode503",
        },
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false", "require_not_maintenance_mode_503"],
            "class": "django.utils.log.AdminEmailHandler",
            "include_html": True,
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
import logging.config

logging.config.dictConfig(LOGGING)

MARKDOWNX_MARKDOWN_EXTENSIONS = ["markdown.extensions.toc"]

TAGGIT_CASE_INSENSITIVE = True

SELENIUM_HEADLESS_MODE = True

# Hexagon size (in meters) according to the zoom level. Adjust ZOOM_TO_HEX_SIZE_MULTIPLIER to simultaneously configure
# all zoom levels

ZOOM_TO_HEX_SIZE_MULTIPLIER = 2
ZOOM_TO_HEX_SIZE_BASELINE = {
    0: 640000,
    1: 320000,
    2: 160000,
    3: 80000,
    4: 40000,
    5: 20000,
    6: 10000,
    7: 5000,
    8: 2500,
    9: 1250,
    10: 675,
    11: 335,
    12: 160,
    13: 80,
    14: 80,
    # At higher zoom levels, the map shows the individual points
}
ZOOM_TO_HEX_SIZE = {
    key: value * ZOOM_TO_HEX_SIZE_MULTIPLIER
    for key, value in ZOOM_TO_HEX_SIZE_BASELINE.items()
}

# The zoom level at which the minimum and maximum values are queried
# That's the only zoom level where this calculation is done
# By consequence, we generate a materialized view for this zoom level, so
# the endpoint has good performances. We initially generated those views at each zoom
# level, but it's lengthy (during import), eats disk space and is unnecessary.
# The test suite also make sure the endpoint works at different zoom levels, so it
# will need to generate more materialized views (so the endpoint works), but it's only
# when running tests and with a tiny amount of data.
ZOOM_LEVEL_FOR_MIN_MAX_QUERY = 8
