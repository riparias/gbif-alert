from dashboard.models import DataImport
from dashboard.utils import human_readable_git_version_number


def latest_data_import_processor(request):
    try:
        data_import = DataImport.objects.latest("end")
    except DataImport.DoesNotExist:
        data_import = None
    return {
        "latest_data_import": data_import,
        "git_version_number": human_readable_git_version_number,
    }
