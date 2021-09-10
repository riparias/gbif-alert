from django.core.paginator import Paginator
from django.http import JsonResponse

from dashboard.models import Species
from dashboard.views.helpers import filtered_occurrences_from_request, extract_int_request


def species_list_json(request):
    return JsonResponse([species.as_dict for species in Species.objects.all()], safe=False)


def occurrences_counter(request):
    """Count the occurrences according to the filters received

    filters: same format than other endpoints: getting occurrences, map tiles, ...
    """
    qs = filtered_occurrences_from_request(request)
    return JsonResponse({'count': qs.count()})


def occurrences_json(request):
    order = request.GET.get('order')
    limit = extract_int_request(request, 'limit')
    page_number = extract_int_request(request, 'page_number')

    occurrences = filtered_occurrences_from_request(request).order_by(order)

    paginator = Paginator(occurrences, limit)

    page = paginator.get_page(page_number)
    occurrences_dicts = [occ.as_dict for occ in page.object_list]

    return JsonResponse({'results': occurrences_dicts,
                         'firstPage': page.paginator.page_range.start,
                         'lastPage': page.paginator.page_range.stop,
                         'totalResultsCount': page.paginator.count})