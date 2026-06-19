"""Helpers functions used by views"""

import ast
import datetime
import logging
from string import Template
from urllib.parse import unquote

from django.db import connection
from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse, QueryDict
from dashboard.models import Observation, User
from dashboard.utils import readable_string
from django.conf import settings

logger = logging.getLogger(__name__)


# The external surface (public/v2 API and the Vue frontend) speaks
# "viewed"/"notViewed"; the internal observation filtering uses "seen"/"unseen".
# Translate the external value to the internal one at each request boundary.
# Unknown/None values mean "no status filter". This is the single source of
# truth for the mapping; keep every boundary (api_v2, map tile endpoints) using
# it so the vocabularies cannot drift apart.
STATUS_API_TO_INTERNAL = {"viewed": "seen", "notViewed": "unseen"}


def api_status_to_internal(api_status: str | None) -> str | None:
    """Map an external status value ("viewed"/"notViewed") to the internal
    "seen"/"unseen". Returns None for None or any unrecognized value."""
    return STATUS_API_TO_INTERNAL.get(api_status) if api_status else None


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


def extract_str_request(request: HttpRequest, param_name: str) -> str | None:
    return _get_querydict_from_request(request).get(param_name, None)


def extract_int_array_request(request: HttpRequest, param_name: str) -> list[int]:
    """Like extract_array_request, but elements are converted to integers"""
    return list(map(lambda e: int(e), extract_array_request(request, param_name)))


def extract_array_request(request: HttpRequest, param_name: str) -> list[str]:
    # Return an array of strings
    # Example:
    #   in: ?speciesIds[]=10&speciesIds[]=12 (params in URL string)
    #   out: ['10', '12']
    # empty params: output is []
    return _get_querydict_from_request(request).getlist(param_name)


def extract_int_request(request: HttpRequest, param_name: str) -> int | None:
    """Returns an integer, or None if the parameter doesn't exist or is 'null'"""
    val = _get_querydict_from_request(request).get(param_name, None)
    if val == "" or val == "null" or val is None:
        return None
    else:
        return int(val)


def extract_date_request(
    request: HttpRequest, param_name: str, date_format="%Y-%m-%d"
) -> datetime.date | None:
    """Return a datetime.date object (or None is the param doesn't exist or is empty)

    format: see https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
    """
    val = _get_querydict_from_request(request).get(param_name, None)

    if val is not None and val != "" and val != "null":
        return datetime.datetime.strptime(val, date_format).date()

    return None


def extract_dict_request(request: HttpRequest, param_name: str) -> dict | None:
    """Returns a dict. The parameter is expected to be URL encoded via  urlencode() or similar

    Edge cases:
    If parameter not set: None
    If not a dict but something else that can be interpreted by literal_eval (see Python doc): None
    May raise ValueError, TypeError, SyntaxError, MemoryError and RecursionError depending on the malformed input.
    """
    val = extract_str_request(request, param_name)
    if val is not None:
        evaluated = ast.literal_eval(unquote(val))
        if isinstance(evaluated, dict):
            return evaluated

    return None


def filtered_observations_from_request(request: HttpRequest) -> QuerySet[Observation]:
    """Takes a request, extract common parameters used to filter observations and return a corresponding QuerySet"""
    (
        species_ids,
        datasets_ids,
        basis_of_record_ids,
        start_date,
        end_date,
        areas_ids,
        status_for_user,
        initial_data_import_ids,
        verified_filter,
        area_filter_mode,
        approaching_distance_km,
    ) = filters_from_request(request)

    user = None
    if request.user.is_authenticated:
        user = request.user

    return Observation.objects.filtered_from_my_params(
        species_ids=species_ids,
        datasets_ids=datasets_ids,
        basis_of_record_ids=basis_of_record_ids,
        start_date=start_date,
        end_date=end_date,
        areas_ids=areas_ids,
        status_for_user=status_for_user,
        initial_data_import_ids=initial_data_import_ids,
        user=user,
        verified_filter=verified_filter,
        area_filter_mode=area_filter_mode,
        approaching_distance_km=approaching_distance_km,
    )


def filters_from_request(
    request: HttpRequest,
) -> tuple[
    list[int],
    list[int],
    list[int],
    datetime.date | None,
    datetime.date | None,
    list[int],
    str | None,
    list[int],
    str | None,
    str,
    float | None,
]:
    species_ids = extract_int_array_request(request, "speciesIds[]")
    datasets_ids = extract_int_array_request(request, "datasetsIds[]")
    basis_of_record_ids = extract_int_array_request(request, "basisOfRecordIds[]")
    start_date = extract_date_request(request, "startDate")
    end_date = extract_date_request(request, "endDate")
    areas_ids = extract_int_array_request(request, "areaIds[]")
    status_for_user = extract_str_request(request, "status")
    initial_data_import_ids = extract_int_array_request(
        request, "initialDataImportIds[]"
    )
    verified_filter = extract_str_request(request, "verifiedFilter")
    raw_mode = extract_str_request(request, "areaFilterMode") or "inside"
    area_filter_mode = raw_mode if raw_mode in ("inside", "approaching", "both") else "inside"
    raw_distance = extract_str_request(request, "approachingDistanceKm")
    approaching_distance_km: float | None = None
    if raw_distance:
        try:
            dist = float(raw_distance)
            if 0 < dist <= 50:
                approaching_distance_km = dist
        except (ValueError, OverflowError):
            pass

    return (
        species_ids,
        datasets_ids,
        basis_of_record_ids,
        start_date,
        end_date,
        areas_ids,
        status_for_user,
        initial_data_import_ids,
        verified_filter,
        area_filter_mode,
        approaching_distance_km,
    )


def model_to_json_list(Model) -> JsonResponse:
    """Return a JSON list for the specific model

    Model instances should have an as_dict property
    """
    return JsonResponse([entry.as_dict for entry in Model.objects.all()], safe=False)


def create_or_refresh_all_materialized_views():
    for hex_size in set(settings.ZOOM_TO_HEX_SIZE.values()):  # set to remove duplicates
        create_or_refresh_single_materialized_view(hex_size)


def create_or_refresh_materialized_views(zoom_levels: list[int]):
    """Create or refresh a bunch of materialized views for a list of zoom levels"""
    for zoom_level in zoom_levels:
        create_or_refresh_single_materialized_view(
            settings.ZOOM_TO_HEX_SIZE[zoom_level]
        )


def create_or_refresh_single_materialized_view(hex_size_meters: int):
    """Create or refresh a single materialized view for a specific hex size in meters"""
    logger.info(
        f"Creating or refreshing materialized view for hex size {hex_size_meters}"
    )

    # Compute hexagon cell coordinates mathematically instead of using ST_HexagonGrid spatial join.
    # For flat-topped hexagons: width = size * 2, height = size * sqrt(3)
    # Horizontal spacing = size * 1.5, vertical spacing = size * sqrt(3)
    # Odd columns are offset by half the vertical spacing.
    sql_template = readable_string(
        Template(
            """
        DROP MATERIALIZED VIEW IF EXISTS hexa_$hex_size_meters;
        CREATE MATERIALIZED VIEW hexa_$hex_size_meters AS (
         WITH params AS (
           SELECT
             $hex_size_meters::float AS size,
             $hex_size_meters * 1.5 AS horiz_spacing,
             $hex_size_meters * sqrt(3.0) AS vert_spacing
         )
         SELECT
           obs.id,
           obs.species_id,
           obs.source_dataset_id,
           obs.basis_of_record_id,
           obs.initial_data_import_id,
           obs.verified,
           obs.date,
           obs.location,
           floor(ST_X(obs.location) / params.horiz_spacing)::int AS hex_col,
           floor((ST_Y(obs.location) / params.vert_spacing) - 0.5 * (floor(ST_X(obs.location) / params.horiz_spacing)::int % 2))::int AS hex_row
         FROM dashboard_observation AS obs, params
        ) WITH NO DATA;

        CREATE INDEX IF NOT EXISTS hexa_${hex_size_meters}_loc_idx ON hexa_$hex_size_meters USING gist (location);
        CREATE INDEX IF NOT EXISTS hexa_${hex_size_meters}_hex_idx ON hexa_$hex_size_meters (hex_col, hex_row);
        CREATE INDEX IF NOT EXISTS hexa_${hex_size_meters}_species_idx ON hexa_$hex_size_meters (species_id);

        REFRESH MATERIALIZED VIEW hexa_$hex_size_meters;
        """
        ).substitute(hex_size_meters=hex_size_meters)
    )

    with connection.cursor() as cursor:
        cursor.execute(sql_template)
