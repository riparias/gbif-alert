from django.http import JsonResponse

from dashboard.models import Species


def species_list_json(request):
    return JsonResponse([species.as_dict for species in Species.objects.all()], safe=False)