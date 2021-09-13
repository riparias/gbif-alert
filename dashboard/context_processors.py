from dashboard.models import DataImport


def latest_data_import_processor(request):
    try:
        data_import = DataImport.objects.latest("end")
    except DataImport.DoesNotExist:
        data_import = None
    return {"latest_data_import": data_import}
