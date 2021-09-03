from django.http import JsonResponse

from dashboard.models import Species


def species_list_json(request):
    data = list(Species.objects.all().values())
    return JsonResponse(data, safe=False)