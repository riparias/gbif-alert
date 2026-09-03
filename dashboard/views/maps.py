"""Observations tile server + related endpoints"""

from django.db import connection, OperationalError, ProgrammingError
from django.http import HttpResponse, JsonResponse, HttpRequest

from dashboard.models import (
    Observation,
    Area,
    AreaPart,
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

_TBL_AREA_PARTS = AreaPart.objects.model._meta.db_table
_TBL_OBS = Observation.objects.model._meta.db_table
_TBL_UNSEEN = ObservationUnseen.objects.model._meta.db_table
_TBL_SPECIES = Species.objects.model._meta.db_table

_SUPPORTED_LANG_CODES = {code[:2] for code, _name in settings.LANGUAGES}

# Half the width of the Web Mercator world, in meters: ST_TileEnvelope's default
# bounds. A tile at zoom z is (2 * this) / 2**z meters wide.
_WEB_MERCATOR_HALF_WIDTH = 20037508.342789244
# ST_AsMVTGeom's default buffer, as a fraction of the tile width (256 / 4096).
_MVT_BUFFER_FRACTION = 256 / 4096

# The tile envelope, grown by `tile_envelope_expand_meters` on each side. The
# observation and area-part bounding-box tests below are what let PostgreSQL
# start from the tile (via the GIST indexes) rather than from the whole filter.
_TILE_ENVELOPE_SQL = (
    "ST_Expand(ST_TileEnvelope(%(zoom)s, %(x)s, %(y)s), "
    "%(tile_envelope_expand_meters)s)"
)


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


def _uses_area_parts(params: dict) -> bool:
    """Whether this query filters through the subdivided area parts.

    Three things depend on this and must agree: the parts table joins into the
    FROM list, the area condition goes in the WHERE clause, and the endpoints
    deduplicate their output (an observation matches once per part it falls
    in). A precomputed buffer (approaching/both modes) filters against one
    prebuilt geometry instead, and needs none of them.
    """
    return bool(params.get("area_ids")) and not params.get("precomputed_area_ewkb")


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
    elif _uses_area_parts(params):
        clauses.append("AND parts.area_id = ANY(%(area_ids)s)")
        if params.get("tile_envelope_expand_meters") is not None:
            # Only the parts around the tile can hold its observations. Without
            # this, a tile of a 67-area alert joined all 2.8k parts against
            # every hexagon of the tile: 1.2M index probes, 3.4 s.
            clauses.append(f"AND parts.geom && {_TILE_ENVELOPE_SQL}")
        clauses.append("AND ST_Intersects(obs.location, parts.geom)")

    if params.get("initial_data_import_ids"):
        clauses.append(
            "AND obs.initial_data_import_id = ANY(%(initial_data_import_ids)s)"
        )
        binds["initial_data_import_ids"] = list(params["initial_data_import_ids"])

    if params.get("verified_filter") == "verified":
        clauses.append("AND obs.verified = true")
    elif params.get("verified_filter") == "unverified":
        clauses.append("AND obs.verified = false")

    # Seen/unseen status, always relative to the requesting user. Both branches
    # are written as a plain condition on (user_id, observation_id) so that
    # dashboard_ou_user_obs_idx (migration 0037) is all Postgres needs. Going
    # through an `id IN (SELECT id FROM <unseen> WHERE user_id = ...)` subquery
    # instead adds a self-join of the unseen table - the index still finds the
    # user's rows, but the plan then walks back to the same table by primary key
    # just to read user_id. On 100k observations / 102k unseen rows that self-
    # join costs 20x the buffers once another filter narrows the tile (1759 ->
    # 83, 0.62ms -> 0.37ms). Same reasoning as in
    # ObservationManager.filtered_from_my_params, which these two clauses must
    # stay equivalent to.
    status = params.get("status")
    if status == "seen":
        # "Seen" is the absence of an unseen record *for this user*: a record
        # belonging to somebody else must not hide the observation here.
        clauses.append(
            f"""AND NOT EXISTS(
            SELECT 1 FROM {_TBL_UNSEEN} ov
            WHERE ov.user_id = %(user_id)s AND ov.observation_id = obs.id)"""
        )
        binds["user_id"] = params["user_id"]
    elif status == "unseen":
        # _build_joins() INNER JOINs the unseen table on observation_id; keeping
        # only this user's rows both applies the filter and guarantees at most
        # one joined row per observation (unique_together on observation+user),
        # so the aggregated endpoints do not double-count.
        clauses.append(f"AND {_TBL_UNSEEN}.user_id = %(user_id)s")
        binds["user_id"] = params["user_id"]

    if params.get("tile_envelope_expand_meters") is not None:
        if params.get("observations_in_tile_envelope", True):
            clauses.append(f"AND obs.location && {_TILE_ENVELOPE_SQL}")
        binds["zoom"] = params["zoom"]
        binds["x"] = params["x"]
        binds["y"] = params["y"]
        binds["tile_envelope_expand_meters"] = params["tile_envelope_expand_meters"]

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
    if _uses_area_parts(params):
        # The subdivided pieces of the selected areas. No ST_Union: the pieces
        # already carry their area_id, so the union that used to run on every
        # request is gone entirely - along with the GEOS TopologyException it
        # raised whenever one of the selected areas was self-intersecting.
        joins.append(f", {_TBL_AREA_PARTS} AS parts")
        binds["area_ids"] = list(params["area_ids"])

    return " ".join(joins), binds


def _filtered_observations_subquery(params: dict) -> tuple[str, dict]:
    """The ``SELECT * FROM <obs> <joins> WHERE (<where>)`` body that selects the
    filtered observations, used as a subquery by the two MVT tile endpoints.
    Returns ``(sql, binds)``."""
    joins_sql, binds = _build_joins(params)
    where_sql, where_binds = _build_where_clause(params)
    binds.update(where_binds)
    # No DISTINCT here, ever. The parts join yields an observation once per
    # part it falls in (overlapping selected areas, points on a cut line), but
    # deduplicating inside this subquery stops PostgreSQL from flattening it:
    # every tile then materialises and sorts *all* matching observations before
    # the tile envelope is applied, then cross-joins them with the hexagons
    # without an index. Measured at 0.4 s -> 7 s per tile for a 152k-observation
    # alert. Each endpoint deduplicates its own, tile-sized output instead. The
    # unseen join needs no deduplication: at most 1:1 thanks to its
    # unique_together plus the user_id condition.
    #
    # An explicit, narrow column list: `id` alone would be ambiguous between
    # obs and species, and the endpoints only read these. The species columns
    # are there for the MVT endpoint's `name` and `vernacular_name_<lang>`.
    columns = ", ".join(
        ["obs.id", "obs.location", "obs.gbif_id", "obs.stable_id", "species.name"]
        + [f"species.vernacular_name_{code}" for code in sorted(_SUPPORTED_LANG_CODES)]
    )
    sql = f"""
        SELECT {columns} FROM {_TBL_OBS} as obs
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


def mvt_tiles_observations(
    request: HttpRequest, zoom: int, x: int, y: int
) -> HttpResponse:
    """Tile server, showing non-aggregated observations. Filters are honoured."""
    lang = get_language() or "en"
    lang_code = lang[:2] if lang[:2] in _SUPPORTED_LANG_CODES else "en"
    vernacular_col = f"vernacular_name_{lang_code}"

    # Restrict the query to what ST_AsMVTGeom keeps: the tile plus its buffer.
    # It clips the rest anyway, but only after every matching observation has
    # been fetched - 1.2 s -> 20 ms per tile on a 152k-observation alert.
    tile_width = 2 * _WEB_MERCATOR_HALF_WIDTH / 2**zoom
    params = {
        **_build_filter_params(request),
        "zoom": zoom,
        "x": x,
        "y": y,
        "tile_envelope_expand_meters": tile_width * _MVT_BUFFER_FRACTION,
    }
    filtered_sql, binds = _filtered_observations_subquery(params)
    binds.update({"zoom": zoom, "x": x, "y": y})
    # See _filtered_observations_subquery: the parts join is the only source
    # of duplicate rows, and by now they are tile-sized.
    distinct = "DISTINCT " if _uses_area_parts(params) else ""

    sql = readable_string(
        f"""
            WITH mvtgeom AS (
                SELECT {distinct}ST_AsMVTGeom(observations.location, ST_TileEnvelope(%(zoom)s, %(x)s, %(y)s)), observations.gbif_id, observations.stable_id, observations.name AS scientific_name, observations.{vernacular_col} AS vernacular_name
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
    hex_size = settings.ZOOM_TO_HEX_SIZE[zoom]
    # ST_HexagonGrid returns every hexagon touching the tile envelope, and this
    # tile owns their full count - the neighbouring tile renders the same
    # hexagon with the same number. So the observations (and area parts) to
    # consider extend past the envelope by however far an edge hexagon sticks
    # out: up to one hexagon *width*, which is twice ST_HexagonGrid's `size`
    # (the circumradius). Expanding by one size, as this used to for the
    # approaching/both modes, silently dropped observations from edge hexagons.
    params = {
        **_build_filter_params(request),
        "zoom": zoom,
        "x": x,
        "y": y,
        "tile_envelope_expand_meters": 2 * hex_size,
    }
    # When joining area parts, the envelope goes on the parts only. Putting it
    # on the observations too makes the planner start from the hexagons and
    # probe the parts once per observation in the tile - 22k probes, 3.4 s at
    # zoom 11 on a 152k-observation alert, against 19 ms when it starts from
    # the handful of parts around the tile. Without parts (no area filter, or a
    # precomputed approaching/both geometry) the hexagons are the only way in,
    # and the envelope helps: 1.3 s -> 1.0 s at zoom 8 in approaching mode.
    params["observations_in_tile_envelope"] = not _uses_area_parts(params)
    filtered_sql, binds = _filtered_observations_subquery(params)
    binds.update({"hex_size_meters": hex_size, "zoom": zoom, "x": x, "y": y})
    # See _filtered_observations_subquery: the parts join can repeat an
    # observation, and COUNT(*) would count it twice.
    count = (
        "COUNT(DISTINCT dashboard_filtered_occ.id)"
        if _uses_area_parts(params)
        else "COUNT(*)"
    )

    grid_sql = f"""
        SELECT {count}, hexes.geom
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

    # Same duplicate rows as the tiles when joining area parts; the colour ramp
    # is scaled from these numbers, so count the way the hexagon tiles do.
    count = "COUNT(DISTINCT obs.id)" if _uses_area_parts(params) else "COUNT(*)"
    sql = readable_string(
        f"""
            WITH grid AS (
                SELECT {count}
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
