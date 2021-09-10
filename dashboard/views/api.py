from django.http import JsonResponse

from dashboard.models import Species
from dashboard.views.helpers import filtered_occurrences_from_request


def species_list_json(request):
    return JsonResponse([species.as_dict for species in Species.objects.all()], safe=False)


def occurrences_counter(request):
    """Count the occurrences according to the filters received

    filters: same format than other endpoints: getting occurrences, map tiles, ...
    """
    qs = filtered_occurrences_from_request(request)
    return JsonResponse({'count': qs.count()})