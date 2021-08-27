from django.http import JsonResponse
from django.shortcuts import render

from dashboard.models import Species


def index(request):
    return render(request, 'dashboard/index.html')


def species_list_json(request):
    data = list(Species.objects.all().values())
    return JsonResponse(data, safe=False)