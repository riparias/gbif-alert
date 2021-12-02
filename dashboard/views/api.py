"""API endpoints are implemented in this file, except maps-related endpoints (see maps.py)

All endpoints that deal with filtered occurrences takes the following GET parameters (all optional, can be combined at will):
    - speciesIds[]: one or several species IDs. Example query string: ?speciesIds[]=1&speciesIds[]=2
    - datasetsIds[]: one or several dataset IDs. Example query string: ?datasetsIds[]=1&datasetsIds[]=2
    - startDate: start date (inclusive), in '%Y-%m-%d' format. Example: 2021-07-31, 1981-08-02
    - endDate: end date (inclusive), in '%Y-%m-%d' format. Example: 2021-07-31, 1981-08-02
"""
from django.core.paginator import Paginator
from django.core.serializers import serialize
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404

from dashboard.models import Species, Dataset, Area
from dashboard.views.helpers import (
    filtered_occurrences_from_request,
    extract_int_request,
)


def _model_to_json_list(Model):
    """Return a JSON list for the specific model

    Model instances should have an as_dict property
    """
    return JsonResponse([entry.as_dict for entry in Model.objects.all()], safe=False)


def species_list_json(_):
    """A list of all species known to the system, in JSON format

    Order: undetermined
    """
    return _model_to_json_list(Species)


def areas_list_json(request):
    """A list of all areas (multypolygons) available to the user.

    Rules:
        - anonymous user: only list global (non-user specific) areas
        - logged-in users: see global and own areas
    """
    areas = Area.objects.all()
    if request.user.is_authenticated:
        areas = [area for area in areas if area.is_available_to(request.user)]
    else:
        areas = [area for area in areas if area.is_global]

    return JsonResponse(
        [area.to_dict(include_geojson=False) for area in areas], safe=False
    )


def area_geojson(request, id: int):
    """Return a specific area as GeoJSON"""
    area = get_object_or_404(Area, pk=id)
    if area.is_available_to(request.user):
        return HttpResponse(
            serialize("geojson", [area]), content_type="application/json"
        )
    else:
        return HttpResponseForbidden()


def datasets_list_json(_):
    """A list of all datasets known to the system, in JSON format

    Order: undetermined
    """
    return _model_to_json_list(Dataset)


def filtered_occurrences_counter_json(request):
    """Count the occurrences according to the filters received

    parameters:
    - filters: same format than other endpoints: getting occurrences, map tiles, ...
    """
    qs = filtered_occurrences_from_request(request)
    return JsonResponse({"count": qs.count()})


def filtered_occurrences_data_page_json(request):
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


def filtered_occurrences_monthly_histogram_json(request):
    """Give the (filtered) number of occurrences per month

    parameters:
    - filters: same format than other endpoints: getting occurrences, map tiles, ...

    Output is chronologically ordered
    """
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
