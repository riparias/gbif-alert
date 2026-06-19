"""Observations tile server + related endpoints"""

from django.db import connection, OperationalError, ProgrammingError
from django.http import HttpResponse, JsonResponse, HttpRequest

from dashboard.models import (
    Observation,
    Area,
    Species,
    ObservationUnseen,
    compute_area_filter_geometry,
)
from django.contrib.gis.db.models.aggregates import Union as AggregateUnion
from dashboard.utils import readable_string
from dashboard.views.helpers import (
    filters_from_request,
    extract_int_request,
    api_status_to_internal,
)
from django.conf import settings
from django.utils.translation import get_language

_TBL_AREAS = Area.objects.model._meta.db_table
_TBL_OBS = Observation.objects.model._meta.db_table
_TBL_UNSEEN = ObservationUnseen.objects.model._meta.db_table
_TBL_SPECIES = Species.objects.model._meta.db_table


# ---------------------------------------------------------------------------
# SQL builders
#
# These assemble the observation-filter SQL as plain psycopg parameterized
# queries (named %(...)s placeholders + a binds dict) instead of jinjasql
# templating.
#
# Security invariant: every *user-derived* value is a bound parameter. The only
# values interpolated into the SQL text are server-controlled identifiers - the
# `_TBL_*` table names (from `Model._meta.db_table`) and, in the endpoints, the
# settings-derived hexagon size and the language vernacular column.
#
# !! IMPORTANT !! Keep the observation filtering here equivalent to what is done
# in views.helpers.filtered_observations_from_request. Otherwise observations
# returned on the map and on other components (table, ...) will be inconsistent.
# ---------------------------------------------------------------------------


def _build_where_clause(params: dict) -> tuple[str, dict]:
    """Build the WHERE-condition fragment and its named bind params.

    Returns ``(sql, binds)`` where ``sql`` is a series of ``AND ...`` conditions
    (with a leading ``1 = 1``) and ``binds`` maps placeholder names to values. A
    condition is only emitted when its filter is present - mirroring the old
    ``{% if ... %}`` guards - so e.g. empty id lists add no clause.
    """
    clauses = ["1 = 1"]
    binds: dict = {}

    if params.get("species_ids"):
        clauses.append("AND obs.species_id = ANY(%(species_ids)s)")
        binds["species_ids"] = list(params["species_ids"])
    if params.get("datasets_ids"):
        clauses.append("AND obs.source_dataset_id = ANY(%(datasets_ids)s)")
        binds["datasets_ids"] = list(params["datasets_ids"])
    if params.get("basis_of_record_ids"):
        clauses.append("AND obs.basis_of_record_id = ANY(%(basis_of_record_ids)s)")
        binds["basis_of_record_ids"] = list(params["basis_of_record_ids"])
    if params.get("start_date"):
        clauses.append("AND obs.date >= TO_DATE(%(start_date)s, 'YYYY-MM-DD')")
        binds["start_date"] = params["start_date"]
    if params.get("end_date"):
        clauses.append("AND obs.date <= TO_DATE(%(end_date)s, 'YYYY-MM-DD')")
        binds["end_date"] = params["end_date"]

    # Area spatial filter. A precomputed buffer geometry (approaching/both
    # modes) takes precedence; otherwise filter against the unioned-areas
    # subquery that _build_joins adds to the FROM list.
    if params.get("precomputed_area_ewkb"):
        clauses.append(
            "AND ST_Within(obs.location, ST_GeomFromEWKB(%(precomputed_area_ewkb)s))"
        )
        binds["precomputed_area_ewkb"] = params["precomputed_area_ewkb"]
    elif params.get("area_ids"):
        clauses.append("AND ST_Within(obs.location, areas.mpoly)")

    if params.get("initial_data_import_ids"):
        clauses.append(
            "AND obs.initial_data_import_id = ANY(%(initial_data_import_ids)s)"
        )
        binds["initial_data_import_ids"] = list(params["initial_data_import_ids"])

    if params.get("verified_filter") == "verified":
        clauses.append("AND obs.verified = true")
    elif params.get("verified_filter") == "unverified":
        clauses.append("AND obs.verified = false")

    status = params.get("status")
    if status == "seen":
        clauses.append(
            f"""AND NOT (EXISTS(
            SELECT (1) FROM {_TBL_UNSEEN} ov WHERE (
                ov.id IN (SELECT ov1.id FROM {_TBL_UNSEEN} ov1 WHERE ov1.user_id = %(user_id)s)
                AND ov.observation_id = obs.id
            ) LIMIT 1))"""
        )
        binds["user_id"] = params["user_id"]
    elif status == "unseen":
        clauses.append(
            f"""AND {_TBL_UNSEEN}.id IN (
                SELECT ov1.id FROM {_TBL_UNSEEN} ov1 WHERE ov1.user_id = %(user_id)s
            )"""
        )
        binds["user_id"] = params["user_id"]

    if params.get("limit_to_tile"):
        clauses.append(
            "AND ST_Within(obs.location, ST_Expand("
            "ST_TileEnvelope(%(zoom)s, %(x)s, %(y)s), %(tile_buffer_meters)s))"
        )
        binds["zoom"] = params["zoom"]
        binds["x"] = params["x"]
        binds["y"] = params["y"]
        binds["tile_buffer_meters"] = params["tile_buffer_meters"]

    # Space-separated: the endpoints flatten the assembled SQL with
    # readable_string(), which strips newlines without inserting a separator.
    return " ".join(clauses), binds


def _build_joins(params: dict) -> tuple[str, dict]:
    """Build the JOIN / FROM-list additions shared by all three endpoints.

    Always LEFT JOINs the species table; adds an INNER JOIN on the unseen table
    for the 'unseen' status filter, and a unioned-areas subquery to the FROM
    list when filtering by area without a precomputed buffer geometry. Returns
    ``(sql, binds)``.
    """
    joins = [f"LEFT JOIN {_TBL_SPECIES} as species ON obs.species_id = species.id"]
    binds: dict = {}

    if params.get("status") == "unseen":
        joins.append(
            f"INNER JOIN {_TBL_UNSEEN} ON obs.id = {_TBL_UNSEEN}.observation_id"
        )
    if params.get("area_ids") and not params.get("precomputed_area_ewkb"):
        joins.append(
            f", (SELECT ST_Union(mpoly) AS mpoly FROM {_TBL_AREAS} "
            f"WHERE {_TBL_AREAS}.id = ANY(%(area_ids)s)) AS areas"
        )
        binds["area_ids"] = list(params["area_ids"])

    return " ".join(joins), binds


def _filtered_observations_subquery(params: dict) -> tuple[str, dict]:
    """The ``SELECT * FROM <obs> <joins> WHERE (<where>)`` body that selects the
    filtered observations, used as a subquery by the two MVT tile endpoints.
    Returns ``(sql, binds)``."""
    joins_sql, binds = _build_joins(params)
    where_sql, where_binds = _build_where_clause(params)
    binds.update(where_binds)
    sql = f"""
        SELECT * FROM {_TBL_OBS} as obs
        {joins_sql}
        WHERE (
            {where_sql}
        )
    """
    return sql, binds


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

    # The frontend sends the external vocabulary ("viewed"/"notViewed");
    # _build_where_clause expects the internal one ("seen"/"unseen"), so
    # translate here. Unrecognized values become None -> no status filter.
    internal_status = api_status_to_internal(status_for_user)
    if internal_status and request.user.is_authenticated:
        params["status"] = internal_status
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

    params = {**_build_filter_params(request), "limit_to_tile": False}
    filtered_sql, binds = _filtered_observations_subquery(params)
    binds.update({"zoom": zoom, "x": x, "y": y})

    sql = readable_string(
        f"""
            WITH mvtgeom AS (
                SELECT ST_AsMVTGeom(observations.location, ST_TileEnvelope(%(zoom)s, %(x)s, %(y)s)), observations.gbif_id, observations.stable_id, observations.name AS scientific_name, observations.{vernacular_col} AS vernacular_name
                FROM ({filtered_sql}) AS observations
            )
            SELECT st_asmvt(mvtgeom.*) FROM mvtgeom;
    """
    )

    return HttpResponse(
        _mvt_query_data(sql, binds),
        content_type="application/vnd.mapbox-vector-tile",
    )


def mvt_tiles_observations_hexagon_grid_aggregated(
    request: HttpRequest, zoom: int, x: int, y: int
) -> HttpResponse:
    """Tile server, showing observations aggregated by hexagon squares. Filters are honoured."""
    filter_params = _build_filter_params(request)

    # For approaching/both modes the geography index returns candidates from the
    # whole dataset, which are then cross-joined with the hex grid
    # (O(candidates * hexes)). Adding an explicit tile envelope filter to WHERE
    # lets PostgreSQL use a BitmapAnd of the geography index AND the SRID 3857
    # tile index, reducing the cross-join to only observations that are actually
    # inside this tile.
    #
    # The envelope is expanded by one hex radius (= hex edge length) so that
    # observations inside edge hexagons that straddle tile boundaries are not
    # truncated. Without the expansion, each tile would only count the half of an
    # edge hexagon's observations that fall within its strict envelope.
    limit_to_tile = bool(filter_params.get("area_ids")) and filter_params.get(
        "area_filter_mode"
    ) in ("approaching", "both")

    params = {
        **filter_params,
        "limit_to_tile": limit_to_tile,
        "zoom": zoom,
        "x": x,
        "y": y,
        "tile_buffer_meters": settings.ZOOM_TO_HEX_SIZE[zoom],
    }
    filtered_sql, binds = _filtered_observations_subquery(params)
    binds.update(
        {
            "hex_size_meters": settings.ZOOM_TO_HEX_SIZE[zoom],
            "zoom": zoom,
            "x": x,
            "y": y,
        }
    )

    grid_sql = f"""
        SELECT COUNT(*), hexes.geom
        FROM
            ST_HexagonGrid(%(hex_size_meters)s, ST_TileEnvelope(%(zoom)s, %(x)s, %(y)s)) AS hexes
            INNER JOIN ({filtered_sql})
        AS dashboard_filtered_occ

        ON ST_Intersects(dashboard_filtered_occ.location, hexes.geom)
        GROUP BY hexes.geom
    """

    sql = readable_string(
        f"""
            WITH grid AS ({grid_sql}),
                 mvtgeom AS (SELECT ST_AsMVTGeom(geom, ST_TileEnvelope(%(zoom)s, %(x)s, %(y)s)) AS geom, count FROM grid)
            SELECT st_asmvt(mvtgeom.*) FROM mvtgeom;
    """
    )

    return HttpResponse(
        _mvt_query_data(sql, binds),
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
    params = _build_filter_params(request)
    joins_sql, binds = _build_joins(params)
    where_sql, where_binds = _build_where_clause(params)
    binds.update(where_binds)

    sql = readable_string(
        f"""
            WITH grid AS (
                SELECT COUNT(*)
                FROM (SELECT * FROM hexa_{hex_size}) AS obs
                    {joins_sql}
                WHERE (
                    {where_sql}
                )
            GROUP BY obs.hex_col, obs.hex_row
            )

            SELECT MIN(count), MAX(count) FROM grid;
            """
    )

    try:
        with _execute_sql(sql, binds) as cursor:
            r = cursor.fetchone()
            return JsonResponse({"min": r[0], "max": r[1]})
    except (ProgrammingError, OperationalError):
        # Materialized views (hexa_*) may not exist in test or fresh environments.
        return JsonResponse({"min": None, "max": None})


def _execute_sql(sql: str, binds: dict):
    """Execute a parameterized query and return the cursor.

    Use as a context manager via the returned cursor; the caller reads results.
    """
    cursor = connection.cursor()
    cursor.execute(sql, binds)
    return cursor


def _mvt_query_data(sql: str, binds: dict):
    """Return binary data for the parameterized SQL query.
    Only for queries that return a binary MVT (i.e. start with "ST_AsMVT")"""
    with _execute_sql(sql, binds) as cursor:
        if cursor.rowcount != 0:
            # psycopg2 returns a bytea column as a memoryview, psycopg3 as bytes.
            # bytes() normalises both to a bytes object.
            return bytes(cursor.fetchone()[0])
        return ""
