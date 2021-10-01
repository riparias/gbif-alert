from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse

from dashboard.models import Species
from dashboard.views.helpers import (
    filtered_occurrences_from_request,
    extract_int_request,
)


def species_list_json(request):
    return JsonResponse(
        [species.as_dict for species in Species.objects.all()], safe=False
    )


def occurrences_counter(request):
    """Count the occurrences according to the filters received

    filters: same format than other endpoints: getting occurrences, map tiles, ...
    """
    qs = filtered_occurrences_from_request(request)
    return JsonResponse({"count": qs.count()})


def occurrences_json(request):
    """Main endpoint to get paginated occurrences (data tables, ...)

    parameters:
    - filters: same format than other endpoints: getting occurrences, map tiles, ...
    - order: optional, occurrences order (passed to QuerySet.order_by)
    - limit: number of occurrences per page
    - page_number: requested page number

    response example:

    {
        "results": [
            {
                "id": 1,
                "lat": "50.489",
                "lon": "5.0951",
                "speciesName": "Elodea nuttallii",
                "date": "2021-09-12",
            },
            {
                "id": 2,
                "lat": "50.647",
                "lon": "4.3597",
                "speciesName": "Heracleum mantegazzianum",
                "date": "2021-09-12",
            },
            {
                "id": 3,
                "lat": "50.647",
                "lon": "4.3597",
                "speciesName": "Heracleum mantegazzianum",
                "date": "2021-09-13",
            },
        ],
        "firstPage": 1,
        "lastPage": 1,
        "totalResultsCount": 3,
    }

    Notes:
        - If the page number is negative or greater than the number of pages, it returns the last page.
        - If no results are returned because of the filtering: totalResultsCount == 0 and results == []
    """

    order = request.GET.get("order")
    limit = extract_int_request(request, "limit")
    page_number = extract_int_request(request, "page_number")

    occurrences = filtered_occurrences_from_request(request)
    if order is not None:
        occurrences = occurrences.order_by(order)

    paginator = Paginator(occurrences, limit)

    page = paginator.get_page(page_number)
    occurrences_dicts = [occ.as_dict for occ in page.object_list]

    return JsonResponse(
        {
            "results": occurrences_dicts,
            "pageNumber": page.number,  # Number of the current page
            "firstPage": page.paginator.page_range.start,
            # page_range is a python range, (last element not included!)
            "lastPage": page.paginator.page_range.stop - 1,
            "totalResultsCount": page.paginator.count,
        }
    )


def occurrences_monthly_histogram_json(request):
    """Give the (filtered) number of occurrences per month"""
    occurrences = filtered_occurrences_from_request(request)

    histogram_data = (
        occurrences.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    return JsonResponse(
        [
            {"year": e["month"].year, "month": e["month"].month, "count": e["total"]}
            for e in histogram_data
        ],
        safe=False,
    )
