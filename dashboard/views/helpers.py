import datetime
from typing import Tuple, List, Optional

from django.contrib.gis.db.models.aggregates import Union
from django.db.models import QuerySet
from django.http import HttpRequest

from dashboard.models import Observation, Area, User, ObservationView


# This class is only defined to make Mypy happy
# see https://github.com/typeddjango/django-stubs#how-can-i-create-a-httprequest-thats-guaranteed-to-have-an-authenticated-user
class AuthenticatedHttpRequest(HttpRequest):
    user: User


def extract_str_request(request: HttpRequest, param_name: str) -> Optional[str]:
    return request.GET.get(param_name, None)


def extract_int_array_request(request: HttpRequest, param_name: str) -> List[int]:
    """Like extract_array_request, but elements are converted to integers"""
    return list(map(lambda e: int(e), extract_array_request(request, param_name)))


def extract_array_request(request: HttpRequest, param_name: str) -> List[str]:
    # Return an array of strings
    # Example:
    #   in: ?speciesIds[]=10&speciesIds[]=12 (params in URL string)
    #   out: ['10', '12']
    # empty params: output is []
    return request.GET.getlist(param_name)


def extract_int_request(request: HttpRequest, param_name: str) -> Optional[int]:
    """Returns an integer, or None if the parameter doesn't exist or is 'null'"""
    val = request.GET.get(param_name, None)
    if val == "" or val == "null" or val is None:
        return None
    else:
        return int(val)


def extract_date_request(
    request: HttpRequest, param_name: str, date_format="%Y-%m-%d"
) -> Optional[datetime.date]:
    """Return a datetime.date object (or None is the param doesn't exist or is empty)

    format: see https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
    """
    val = request.GET.get(param_name, None)

    if val is not None and val != "" and val != "null":
        return datetime.datetime.strptime(val, date_format).date()

    return None


def filtered_observations_from_request(request: HttpRequest) -> QuerySet[Observation]:
    """Takes a request, extract common parameters used to filter observations and return a corresponding QuerySet"""
    (
        species_ids,
        datasets_ids,
        start_date,
        end_date,
        area_ids,
        status_for_user,
    ) = filters_from_request(request)

    # !! IMPORTANT !! Make sure the observation filtering here is equivalent to what's done in
    # views.maps.JINJASQL_FRAGMENT_FILTER_OBSERVATIONS. Otherwise, observations returned on the map and on other
    # components (table, ...) will be inconsistent.
    # !! If adding new filters, make also sure they are properly documented in the docstrings of "api.py"
    qs = Observation.objects.all()

    if species_ids:
        qs = qs.filter(species_id__in=species_ids)
    if datasets_ids:
        qs = qs.filter(source_dataset_id__in=datasets_ids)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    if area_ids:
        combined_areas = Area.objects.filter(pk__in=area_ids).aggregate(
            area=Union("mpoly")
        )["area"]
        qs = qs.filter(location__within=combined_areas)
    if status_for_user and request.user.is_authenticated:
        ov = ObservationView.objects.filter(user=request.user)
        if status_for_user == "seen":
            qs = qs.filter(observationview__in=ov)
        elif status_for_user == "unseen":
            qs = qs.exclude(observationview__in=ov)

    return qs


def filters_from_request(
    request: HttpRequest,
) -> Tuple[
    List[int],
    List[int],
    Optional[datetime.date],
    Optional[datetime.date],
    List[int],
    Optional[str],
]:
    species_ids = extract_int_array_request(request, "speciesIds[]")
    datasets_ids = extract_int_array_request(request, "datasetsIds[]")
    start_date = extract_date_request(request, "startDate")
    end_date = extract_date_request(request, "endDate")
    area_ids = extract_int_array_request(request, "areaIds[]")
    status_for_user = extract_str_request(request, "status")

    return species_ids, datasets_ids, start_date, end_date, area_ids, status_for_user
