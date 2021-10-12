from django.shortcuts import render, get_object_or_404

from dashboard.models import DataImport, Occurrence


def index_page(request):
    return render(request, "dashboard/index.html")


def about_page(request):
    data_imports = DataImport.objects.all().order_by("-start")
    return render(request, "dashboard/about.html", {"data_imports": data_imports})


def occurrence_details_page(request, pk):
    occurrence = get_object_or_404(Occurrence, pk=pk)
    return render(
        request, "dashboard/occurrence_details.html", {"occurrence": occurrence}
    )
