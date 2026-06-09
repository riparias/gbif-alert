"""Observations tile server + related endpoints"""

from django.db import connection, OperationalError, ProgrammingError
from django.http import HttpResponse, JsonResponse, HttpRequest
from jinjasql import JinjaSql

from dashboard.models import (
    Observation,
    Area,
    Species,
    ObservationUnseen,
    compute_area_filter_geometry,
)
from django.contrib.gis.db.models.aggregates import Union as AggregateUnion
from dashboard.utils import readable_string
from dashboard.views.helpers import filters_from_request, extract_int_request
from django.conf import settings
from django.utils.translation import get_language

_TBL_AREAS = Area.objects.model._meta.db_table
_TBL_OBS = Observation.objects.model._meta.db_table
_TBL_UNSEEN = ObservationUnseen.objects.model._meta.db_table
_TBL_SPECIES = Species.objects.model._meta.db_table


# !! IMPORTANT !! Make sure the observation filtering here is equivalent to what's done in
# other places (views.helpers.filtered_observations_from_request). Otherwise, observations returned on the map and on
# other components (table, ...) will be inconsistent.
WHERE_CLAUSE = readable_string(
    f"""
        1 = 1
        {{% if species_ids %}}
            AND obs.species_id IN {{{{ species_ids | inclause }}}}
        {{% endif %}}
        {{% if datasets_ids %}}
            AND obs.source_dataset_id IN {{{{ datasets_ids | inclause }}}}
        {{% endif %}}
        {{% if basis_of_record_ids %}}
            AND obs.basis_of_record_id IN {{{{ basis_of_record_ids | inclause }}}}
        {{% endif %}}
        {{% if start_date %}}
            AND obs.date >= TO_DATE({{{{ start_date }}}}, 'YYYY-MM-DD')
        {{% endif %}}
        {{% if end_date %}}
            AND obs.date <= TO_DATE({{{{ end_date }}}}, 'YYYY-MM-DD')
        {{% endif %}}
        {{% if precomputed_area_ewkb %}}
            AND ST_Within(obs.location, ST_GeomFromEWKB({{{{ precomputed_area_ewkb }}}}))
        {{% elif area_ids %}}
            AND ST_Within(obs.location, areas.mpoly)
        {{% endif %}}
        {{% if initial_data_import_ids %}}
            AND obs.initial_data_import_id IN {{{{ initial_data_import_ids | inclause }}}}
        {{% endif %}}
        {{% if verified_filter == 'verified' %}}
            AND obs.verified = true
        {{% endif %}}
        {{% if verified_filter == 'unverified' %}}
            AND obs.verified = false
        {{% endif %}}
        {{% if status == 'seen' %}}
            AND NOT (EXISTS(
            SELECT (1) FROM {_TBL_UNSEEN} ov WHERE (
                ov.id IN (SELECT ov1.id FROM {_TBL_UNSEEN} ov1 WHERE ov1.user_id = {{{{ user_id }}}})
                AND ov.observation_id = obs.id
            ) LIMIT 1))
        {{% endif %}}
        {{% if status == 'unseen' %}}
            AND {_TBL_UNSEEN}.id IN (
                SELECT ov1.id FROM {_TBL_UNSEEN} ov1 WHERE ov1.user_id = {{{{ user_id }}}}
            )
        {{% endif %}}
        {{% if limit_to_tile %}}
            AND ST_Within(obs.location, ST_Expand(ST_TileEnvelope({{{{ zoom }}}}, {{{{ x }}}}, {{{{ y }}}}), {{{{ tile_buffer_meters }}}}))
        {{% endif %}}
"""
)

JINJASQL_FRAGMENT_FILTER_OBSERVATIONS = f"""
    SELECT * FROM {_TBL_OBS} as obs
    LEFT JOIN {_TBL_SPECIES} as species
    ON obs.species_id = species.id
    {{% if status == 'unseen' %}}
        INNER JOIN {_TBL_UNSEEN}
        ON obs.id = {_TBL_UNSEEN}.observation_id
    {{% endif %}}

    {{% if area_ids and not precomputed_area_ewkb %}}
    , (SELECT ST_Union(mpoly) AS mpoly FROM {_TBL_AREAS} WHERE {_TBL_AREAS}.id IN {{{{ area_ids | inclause }}}}) AS areas
    {{% endif %}}
    WHERE (
        {WHERE_CLAUSE}
    )
"""

JINJASQL_FRAGMENT_AGGREGATED_GRID = f"""
    SELECT COUNT(*), hexes.geom
    FROM
        ST_HexagonGrid({{{{ hex_size_meters }}}}, ST_TileEnvelope({{{{ zoom }}}}, {{{{ x }}}}, {{{{ y }}}})) AS hexes
        INNER JOIN ({JINJASQL_FRAGMENT_FILTER_OBSERVATIONS})
    AS dashboard_filtered_occ

    ON ST_Intersects(dashboard_filtered_occ.location, hexes.geom)
    GROUP BY hexes.geom
"""


def _build_filter_params(request: HttpRequest) -> dict:
    """Build common SQL filter params from the request.

    Returns a dict with species_ids, datasets_ids, area_ids,
    initial_data_import_ids, and optionally status/user_id/start_date/end_date.
    """
    (
        species_ids,
        datasets_ids,
        basis_of_record_ids,
        start_date,
        end_date,
        area_ids,
        status_for_user,
        initial_data_import_ids,
        verified_filter,
        area_filter_mode,
        approaching_distance_km,
    ) = filters_from_request(request)

    # Pre-compute the buffer geometry for approaching/both modes so that
    # the tile queries use ST_Within against a pre-built SRID 3857 polygon
    # instead of computing ST_DWithin(geography) per row.
    precomputed_area_ewkb = None
    if (
        area_ids
        and area_filter_mode in ("approaching", "both")
        and approaching_distance_km
    ):
        combined_areas = Area.objects.filter(pk__in=area_ids).aggregate(
            area=AggregateUnion("mpoly")
        )["area"]
        if combined_areas:
            precomputed_area_ewkb = compute_area_filter_geometry(
                combined_areas, area_filter_mode, approaching_distance_km
            )

    params: dict = {
        "species_ids": species_ids,
        "datasets_ids": datasets_ids,
        "basis_of_record_ids": basis_of_record_ids,
        "area_ids": area_ids,
        "initial_data_import_ids": initial_data_import_ids,
        "verified_filter": verified_filter,
        "area_filter_mode": area_filter_mode,
        "approaching_distance_km": approaching_distance_km,
        "precomputed_area_ewkb": precomputed_area_ewkb,
    }

    if status_for_user and request.user.is_authenticated:
        params["status"] = status_for_user
        params["user_id"] = request.user.pk

    if start_date is not None:
        params["start_date"] = start_date.strftime("%Y-%m-%d")
    if end_date is not None:
        params["end_date"] = end_date.strftime("%Y-%m-%d")

    return params


_SUPPORTED_LANG_CODES = {code[:2] for code, _name in settings.LANGUAGES}


def mvt_tiles_observations(
    request: HttpRequest, zoom: int, x: int, y: int
) -> HttpResponse:
    """Tile server, showing non-aggregated observations. Filters are honoured."""
    lang = get_language() or "en"
    lang_code = lang[:2] if lang[:2] in _SUPPORTED_LANG_CODES else "en"
    vernacular_col = f"vernacular_name_{lang_code}"

    sql_template = readable_string(
        f"""
            WITH mvtgeom AS (
                SELECT ST_AsMVTGeom(observations.location, ST_TileEnvelope({{{{ zoom }}}}, {{{{ x }}}}, {{{{ y }}}})), observations.gbif_id, observations.stable_id, observations.name AS scientific_name, observations.{vernacular_col} AS vernacular_name
                FROM ({JINJASQL_FRAGMENT_FILTER_OBSERVATIONS}) AS observations
            )
            SELECT st_asmvt(mvtgeom.*) FROM mvtgeom;
    """
    )

    sql_params = {
        **_build_filter_params(request),
        "limit_to_tile": False,
        "zoom": zoom,
        "x": x,
        "y": y,
    }

    return HttpResponse(
        _mvt_query_data(sql_template, sql_params),
        content_type="application/vnd.mapbox-vector-tile",
    )


def mvt_tiles_observations_hexagon_grid_aggregated(
    request: HttpRequest, zoom: int, x: int, y: int
) -> HttpResponse:
    """Tile server, showing observations aggregated by hexagon squares. Filters are honoured."""
    sql_template = readable_string(
        f"""
            WITH grid AS ({JINJASQL_FRAGMENT_AGGREGATED_GRID}),
                 mvtgeom AS (SELECT ST_AsMVTGeom(geom, ST_TileEnvelope({{{{ zoom }}}}, {{{{ x }}}}, {{{{ y }}}})) AS geom, count FROM grid)
            SELECT st_asmvt(mvtgeom.*) FROM mvtgeom;
    """
    )

    filter_params = _build_filter_params(request)
    sql_params = {
        **filter_params,
        "hex_size_meters": settings.ZOOM_TO_HEX_SIZE[zoom],
        "zoom": zoom,
        "x": x,
        "y": y,
        # For approaching/both modes the geography index returns candidates from the whole
        # dataset, which are then cross-joined with the hex grid (O(candidates * hexes)).
        # Adding an explicit tile envelope filter to WHERE lets PostgreSQL use a BitmapAnd
        # of the geography index AND the SRID 3857 tile index, reducing the cross-join to
        # only observations that are actually inside this tile.
        #
        # The envelope is expanded by one hex radius (= hex edge length) so that
        # observations inside edge hexagons that straddle tile boundaries are not
        # truncated. Without the expansion, each tile would only count the half of an
        # edge hexagon's observations that fall within its strict envelope.
        "limit_to_tile": (
            bool(filter_params.get("area_ids"))
            and filter_params.get("area_filter_mode") in ("approaching", "both")
        ),
        "tile_buffer_meters": settings.ZOOM_TO_HEX_SIZE[zoom],
    }

    return HttpResponse(
        _mvt_query_data(sql_template, sql_params),
        content_type="application/vnd.mapbox-vector-tile",
    )


def observation_min_max_in_hex_grid_json(request: HttpRequest):
    """Return the min, max observations count per hexagon, according to the zoom level. JSON format.

    This can be useful to dynamically color the grid according to the count
    """
    zoom = extract_int_request(request, "zoom")
    if zoom is None:
        return JsonResponse({"error": "zoom parameter is required"}, status=400)

    hex_size = settings.ZOOM_TO_HEX_SIZE[zoom]
    sql_template = readable_string(
        f"""
            WITH grid AS (
                SELECT COUNT(*)
                FROM (SELECT * FROM hexa_{hex_size}) AS obs
                    LEFT JOIN dashboard_species as species ON obs.species_id = species.id

                    {{% if status == 'unseen' %}}
                        INNER JOIN {_TBL_UNSEEN}
                        ON obs.id = {_TBL_UNSEEN}.observation_id
                    {{% endif %}}
                    {{% if area_ids and not precomputed_area_ewkb %}}
                    , (SELECT ST_Union(mpoly) AS mpoly FROM {_TBL_AREAS} WHERE {_TBL_AREAS}.id IN {{{{ area_ids | inclause }}}}) AS areas
                    {{% endif %}}
                WHERE (
                    {WHERE_CLAUSE}
                )
            GROUP BY obs.hex_col, obs.hex_row
            )

            SELECT MIN(count), MAX(count) FROM grid;
            """
    )

    sql_params = _build_filter_params(request)

    try:
        with _execute_jinjasql(sql_template, sql_params) as cursor:
            r = cursor.fetchone()
            return JsonResponse({"min": r[0], "max": r[1]})
    except (ProgrammingError, OperationalError):
        # Materialized views (hexa_*) may not exist in test or fresh environments.
        return JsonResponse({"min": None, "max": None})


def _execute_jinjasql(template: str, params: dict):
    """Prepare a JinjaSql template and execute it, returning (cursor, connection).

    Use as a context manager via the returned cursor's connection.
    The caller is responsible for reading results from the cursor.
    """
    j = JinjaSql()
    query, bind_params = j.prepare_query(template, params)
    cursor = connection.cursor()
    cursor.execute(query, bind_params)
    return cursor


def _mvt_query_data(sql_template: str, sql_params: dict):
    """Return binary data for the SQL query defined by sql_template and sql_params.
    Only for queries that returns a binary MVT (i.e. starts with "ST_AsMVT")"""
    with _execute_jinjasql(sql_template, sql_params) as cursor:
        if cursor.rowcount != 0:
            # psycopg2 returns a bytea column as a memoryview, psycopg3 as bytes.
            # bytes() normalises both to a bytes object.
            return bytes(cursor.fetchone()[0])
        return ""
