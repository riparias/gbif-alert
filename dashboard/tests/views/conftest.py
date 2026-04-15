import pytest


@pytest.fixture(autouse=True)
def use_static_files_storage(settings):
    """Use non-hashed static file storage for all view tests.

    Without this, ManifestStaticFilesStorage generates hashed URLs that the
    Django test client cannot resolve, causing template rendering failures.
    """
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )
