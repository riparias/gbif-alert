"""Internal API endpoints are implemented in this file, except maps-related endpoints (see maps.py)

All endpoints that deal with filtered observations takes the following GET parameters (all optional, can be combined at
will):
    - speciesIds[]: one or several species IDs. Example query string: ?speciesIds[]=1&speciesIds[]=2
    - datasetsIds[]: one or several dataset IDs. Example query string: ?datasetsIds[]=1&datasetsIds[]=2
    - startDate: start date (inclusive), in '%Y-%m-%d' format. Example: 2021-07-31, 1981-08-02
    - endDate: end date (inclusive), in '%Y-%m-%d' format. Example: 2021-07-31, 1981-08-02
    - areaIds[]: one or several area IDs. Same format than speciesIds and datasetsIds
    - initialDataImportIds[]: one or several data import. Same format than speciesIds, datasetsIds and areaIds
    - status_for_user: seen | unseen. Ignored for anonymous users. If the parameter is not set or is set to any other
      value than seen or unseen, filtering is not applied
"""
from __future__ import annotations

import json
from typing import List

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.serializers import serialize
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import (
    JsonResponse,
    HttpResponseForbidden,
    HttpResponse,
    HttpRequest,
    HttpResponseNotFound,
)
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from dashboard.models import (
    Dataset,
    Area,
    Alert,
    DataImport,
    User,
)
from dashboard.views.helpers import (
    filtered_observations_from_request,
    extract_int_request,
    AuthenticatedHttpRequest,
    model_to_json_list,
)
from dashboard.views.jobs import mark_many_observations_as_seen


def dataimports_list_json(_) -> JsonResponse:
    """A list of all data imports known to the system, in JSON format

    Order: undetermined
    """
    return model_to_json_list(DataImport)


def areas_list_json(request: HttpRequest) -> JsonResponse:
    """A list of all areas (multipolygons) available to the user.

    Rules:
        - anonymous user: only list public (non-user specific) areas
        - logged-in users: see public and own areas
    """
    areas = Area.objects.available_to(request.user)

    return JsonResponse(
        [area.to_dict(include_geojson=False) for area in areas], safe=False
    )


def area_geojson(request: HttpRequest, id: int):
    """Return a specific area as GeoJSON"""
    area = get_object_or_404(Area, pk=id)
    if area.is_available_to(request.user):
        return HttpResponse(
            serialize("geojson", [area]), content_type="application/json"
        )
    else:
        return HttpResponseForbidden()


def datasets_list_json(_) -> JsonResponse:
    """A list of all datasets known to the system, in JSON format

    Order: undetermined
    """
    return model_to_json_list(Dataset)


def filtered_observations_counter_json(request: HttpRequest) -> JsonResponse:
    """Count the observations according to the filters received

    parameters:
    - filters: same format than other endpoints: getting observations, map tiles, ...
    """
    qs = filtered_observations_from_request(request)
    return JsonResponse({"count": qs.count()})


def filtered_observations_data_page_json(request: HttpRequest) -> JsonResponse:
    """Main endpoint to get paginated observations (data tables, ...)

    parameters:
    - filters: same format than other endpoints: getting observations, map tiles, ...
    - order: optional, observations order (passed to QuerySet.order_by)
    - limit: number of observations per page
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
    if limit is None:
        limit = 50
    page_number = extract_int_request(request, "page_number")

    observations = filtered_observations_from_request(request)
    if order is not None:
        observations = observations.order_by(order)

    paginator = Paginator(observations, limit)

    page = paginator.get_page(page_number)

    return JsonResponse(
        {
            "results": [obs.as_dict(for_user=request.user) for obs in page.object_list],
            "pageNumber": page.number,  # Number of the current page
            "firstPage": page.paginator.page_range.start,
            # page_range is a python range, (last element not included!)
            "lastPage": page.paginator.page_range.stop - 1,
            "totalResultsCount": page.paginator.count,
        }
    )


def filtered_observations_monthly_histogram_json(request: HttpRequest):
    """Give the (filtered) number of observations per month

    parameters:
    - filters: same format than other endpoints: getting observations, map tiles, ...

    Output is chronologically ordered
    """
    observations = filtered_observations_from_request(request)

    histogram_data = (
        observations.annotate(month=TruncMonth("date"))
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


@login_required
def filtered_observations_mark_as_seen(
    request: AuthenticatedHttpRequest,
) -> JsonResponse | HttpResponseForbidden:
    """Mark multiple observations as seen by the current user. Take the same filters as the other observations API"""
    if request.method == "POST":
        observations = filtered_observations_from_request(request)
        mark_many_observations_as_seen.delay(observations, request.user)
        return JsonResponse({"queued": True})

    return HttpResponseForbidden()


@login_required
def alert_as_filters(
    request: AuthenticatedHttpRequest,
) -> JsonResponse | HttpResponseForbidden:
    alert_id = extract_int_request(request, "alert_id")
    alert = get_object_or_404(Alert, id=alert_id)

    if alert.user == request.user:
        return JsonResponse(alert.as_dashboard_filters)
    else:
        return HttpResponseForbidden()


def _create_or_update_alert(
    alert_name: str,
    species_ids: List[int],
    area_ids: List[int],
    dataset_ids: List[int],
    email_notifications_frequency: str,
    user: User,
    alert_id: int = None,
) -> JsonResponse:
    """Create or update an alert, depending on the alert_id value"""
    if alert_id:
        alert = get_object_or_404(Alert.objects.filter(user=user), id=alert_id)
    else:
        alert = Alert(user=user)

    alert.name = alert_name
    alert.email_notifications_frequency = email_notifications_frequency

    errors = {}

    if len(species_ids) == 0:  # This is not catch by the model validation
        errors["species"] = [_("At least one species must be selected")]

    try:
        alert.full_clean()
    except ValidationError as e:
        errors = errors | e.message_dict

    if not errors:
        alert.save()

        # Finally add the m2m relations
        alert.species.clear()
        alert.species.add(*species_ids)
        alert.areas.clear()
        alert.areas.add(*area_ids)
        alert.datasets.clear()
        alert.datasets.add(*dataset_ids)

    return JsonResponse(
        {"alertId": alert.pk, "success": len(errors) == 0, "errors": errors}
    )


@login_required
def alert(
    request: AuthenticatedHttpRequest,
) -> JsonResponse | HttpResponseForbidden | HttpResponseNotFound:
    """This endpoint allows to create a new alert (if alert_id is not set), get details about an existing one and fially update it"""
    if request.method == "GET":
        alert_id = extract_int_request(request, "alert_id")
        alert = get_object_or_404(Alert.objects.filter(user=request.user), id=alert_id)
        return JsonResponse(alert.as_dict)
    elif request.method == "POST":
        alert_data = json.loads(request.body.decode("utf-8"))
        try:
            alert_id = alert_data["id"]
        except KeyError:
            alert_id = None

        return _create_or_update_alert(
            alert_name=alert_data["name"],
            species_ids=alert_data["speciesIds"],
            area_ids=alert_data["areaIds"],
            dataset_ids=alert_data["datasetIds"],
            email_notifications_frequency=alert_data["emailNotificationsFrequency"],
            user=request.user,
            alert_id=alert_id,
        )


def available_alert_intervals(_: HttpRequest) -> JsonResponse:
    intervals = Alert.EMAIL_NOTIFICATION_CHOICES

    intervals_as_objects = [
        {"id": interval[0], "label": interval[1]} for interval in intervals
    ]

    return JsonResponse(intervals_as_objects, safe=False)


@login_required
def suggest_alert_name(request: AuthenticatedHttpRequest) -> JsonResponse:
    """Suggest an alert name based on the user's existing alerts"""
    alert_number = 1
    existing_alert_names = Alert.objects.filter(user=request.user).values_list(
        "name", flat=True
    )
    while f"My alert #{alert_number}" in existing_alert_names:
        alert_number += 1

    return JsonResponse({"name": f"My alert #{alert_number}"})
