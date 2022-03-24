"""Helpers functions used by views"""

import ast
import datetime
from typing import Tuple, List, Optional, Dict
from urllib.parse import unquote

from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse, QueryDict

from dashboard.models import Observation, User


# This class is only defined to make Mypy happy
# see https://github.com/typeddjango/django-stubs#how-can-i-create-a-httprequest-thats-guaranteed-to-have-an-authenticated-user
class AuthenticatedHttpRequest(HttpRequest):
    user: User


def _get_querydict_from_request(request: HttpRequest) -> QueryDict:
    """Allows to transparently get parameters from GET and POST requests

    For POST requests, the body contains a string formatted exactly like the querystring would be in a GET request
    """
    if request.method == "GET":
        return request.GET
    else:
        return QueryDict(query_string=request.body)


def extract_str_request(request: HttpRequest, param_name: str) -> Optional[str]:
    return _get_querydict_from_request(request).get(param_name, None)


def extract_int_array_request(request: HttpRequest, param_name: str) -> List[int]:
    """Like extract_array_request, but elements are converted to integers"""
    return list(map(lambda e: int(e), extract_array_request(request, param_name)))


def extract_array_request(request: HttpRequest, param_name: str) -> List[str]:
    # Return an array of strings
    # Example:
    #   in: ?speciesIds[]=10&speciesIds[]=12 (params in URL string)
    #   out: ['10', '12']
    # empty params: output is []
    return _get_querydict_from_request(request).getlist(param_name)


def extract_int_request(request: HttpRequest, param_name: str) -> Optional[int]:
    """Returns an integer, or None if the parameter doesn't exist or is 'null'"""
    val = _get_querydict_from_request(request).get(param_name, None)
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
    val = _get_querydict_from_request(request).get(param_name, None)

    if val is not None and val != "" and val != "null":
        return datetime.datetime.strptime(val, date_format).date()

    return None


def extract_dict_request(request: HttpRequest, param_name: str) -> Optional[Dict]:
    """Returns a dict. The parameter is expected to be URL encoded via  urlencode() or similar

    Edge cases:
    If parameter not set: None
    If not a dict but something else that can be interpreted by literal_eval (see Python doc): None
    May raise ValueError, TypeError, SyntaxError, MemoryError and RecursionError depending on the malformed input.
    """
    val = extract_str_request(request, param_name)
    if val is not None:
        evaluated = ast.literal_eval(unquote(val))
        if isinstance(evaluated, Dict):
            return evaluated

    return None


def filtered_observations_from_request(request: HttpRequest) -> QuerySet[Observation]:
    """Takes a request, extract common parameters used to filter observations and return a corresponding QuerySet"""
    (
        species_ids,
        datasets_ids,
        start_date,
        end_date,
        areas_ids,
        status_for_user,
        initial_data_import_ids,
    ) = filters_from_request(request)

    user = None
    if request.user.is_authenticated:
        user = request.user

    return Observation.objects.filtered_from_my_params(
        species_ids=species_ids,
        datasets_ids=datasets_ids,
        start_date=start_date,
        end_date=end_date,
        areas_ids=areas_ids,
        status_for_user=status_for_user,
        initial_data_import_ids=initial_data_import_ids,
        user=user,
    )


def filters_from_request(
    request: HttpRequest,
) -> Tuple[
    List[int],
    List[int],
    Optional[datetime.date],
    Optional[datetime.date],
    List[int],
    Optional[str],
    List[int],
]:
    species_ids = extract_int_array_request(request, "speciesIds[]")
    datasets_ids = extract_int_array_request(request, "datasetsIds[]")
    start_date = extract_date_request(request, "startDate")
    end_date = extract_date_request(request, "endDate")
    areas_ids = extract_int_array_request(request, "areaIds[]")
    status_for_user = extract_str_request(request, "status")
    initial_data_import_ids = extract_int_array_request(
        request, "initialDataImportIds[]"
    )

    return (
        species_ids,
        datasets_ids,
        start_date,
        end_date,
        areas_ids,
        status_for_user,
        initial_data_import_ids,
    )


def model_to_json_list(Model) -> JsonResponse:
    """Return a JSON list for the specific model

    Model instances should have an as_dict property
    """
    return JsonResponse([entry.as_dict for entry in Model.objects.all()], safe=False)
