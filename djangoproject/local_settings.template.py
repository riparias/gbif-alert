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
        "NAME": "riparias-early-warning-webapp",
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
EMAIL_SUBJECT_PREFIX = "[dev-alert.riparias.be] "
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "info@dev-alert.riparias.be"  # Used for normal messages
SERVER_EMAIL = "info@dev-alert.riparias.be"  # Used to contact admins for errors, ...

ADMINS = [
    ("Nicolas", "nicolas.noe@inbo.be"),
]

# A Gbif.org account is necessary to automatically download observations via the `import_observations` command
RIPARIAS["GBIF_USERNAME"] = "xxx"
RIPARIAS["GBIF_PASSWORD"] = "yyy"
