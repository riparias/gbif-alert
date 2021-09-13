from django.shortcuts import render

from dashboard.models import DataImport


def index(request):
    return render(request, "dashboard/index.html")


def about(request):
    data_imports = DataImport.objects.all().order_by("-start")
    return render(request, "dashboard/about.html", {"data_imports": data_imports})
