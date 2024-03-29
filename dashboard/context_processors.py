from django.conf import settings as django_settings
from django.http import HttpRequest

from dashboard.models import DataImport
from dashboard.utils import human_readable_git_version_number
from page_fragments.models import NEWS_PAGE_IDENTIFIER


def latest_data_import_processor(_: HttpRequest):
    try:
        data_import: DataImport | None = DataImport.objects.latest("id")
    except DataImport.DoesNotExist:
        data_import = None
    return {
        "latest_data_import": data_import,
        "git_version_number": human_readable_git_version_number,
    }


def gbif_alert_various(_: HttpRequest):
    return {
        "gbif_alert_news_page_fragment_id": NEWS_PAGE_IDENTIFIER,
    }


def gbif_alert_settings(_: HttpRequest):
    return {
        "gbif_alert_settings": django_settings.GBIF_ALERT,
    }
