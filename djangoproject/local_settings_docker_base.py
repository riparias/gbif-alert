from .settings import *

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "pteroisdb",
        "USER": "pteroisdb",
        "PASSWORD": "pteroisdb",
        "HOST": "db",
    }
}

# Redis configuration for django-rq
RQ_QUEUES = {
    "default": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        #        "PASSWORD": "some-password",
        "DEFAULT_TIMEOUT": 360,
    },
}

ALLOWED_HOSTS = ["0.0.0.0", "localhost"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"