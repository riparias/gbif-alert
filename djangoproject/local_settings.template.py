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

# A Gbif.org is necessary to automatically download occurrences via the `import_occurrences` command
RIPARIAS["GBIF_USERNAME"] = "xxx"
RIPARIAS["GBIF_PASSWORD"] = "yyy"
