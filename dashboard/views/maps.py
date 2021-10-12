from string import Template

from django.db import connection
from django.http import HttpResponse, JsonResponse
from jinjasql import JinjaSql

from dashboard.models import Occurrence
from dashboard.utils import readable_string
from dashboard.views.helpers import filters_from_request, extract_int_request

OCCURRENCES_TABLE_NAME = Occurrence.objects.model._meta.db_table
OCCURRENCES_FIELD_NAME_POINT = "location"

# ! Make sure the following formats are in sync
DB_DATE_EXCHANGE_FORMAT_PYTHON = "%Y-%m-%d"  # To be passed to strftime()
DB_DATE_EXCHANGE_FORMAT_POSTGRES = "YYYY-MM-DD"  # To be used in SQL queries

# Hexagon size (in meters) according to the zoom level. Adjust ZOOM_TO_HEX_SIZE_MULTIPLIER to simultaneously configure
# all zoom levels
ZOOM_TO_HEX_SIZE_MULTIPLIER = 2
ZOOM_TO_HEX_SIZE_BASELINE = {
    1: 320000,
    2: 160000,
    3: 80000,
    4: 40000,
    5: 20000,
    6: 10000,
    7: 5000,
    8: 2500,
    9: 1250,
    10: 675,
    11: 335,
    12: 160,
    13: 80,
    14: 40,
    15: 20,
    16: 10,
    17: 5,
    18: 5,
    19: 5,
    20: 5,
}
ZOOM_TO_HEX_SIZE = {
    key: value * ZOOM_TO_HEX_SIZE_MULTIPLIER
    for key, value in ZOOM_TO_HEX_SIZE_BASELINE.items()
}

# !! IMPORTANT !! Make sure the occurrence filtering here is equivalent to what's done in
# other places (views.helpers.filtered_occurrences_from_request). Otherwise, occurrences returned on the map and on
# other components (table, ...) will be inconsistent.
JINJASQL_FRAGMENT_FILTER_OCCURRENCES = Template(
    """
    SELECT * FROM $occurrences_table_name as occ
    WHERE (
        1 = 1
        {% if species_ids %}
            AND occ.species_id IN {{ species_ids | inclause }}
        {% endif %}
        {% if datasets_ids %}
            AND occ.source_dataset_id IN {{ datasets_ids | inclause }}
        {% endif %}
        {% if start_date %}
            AND occ.date >= TO_DATE({{ start_date }}, '$date_format')
        {% endif %}
        {% if end_date %}
            AND occ.date <= TO_DATE({{ end_date }}, '$date_format')
        {% endif %}
    )
"""
).substitute(
    occurrences_table_name=OCCURRENCES_TABLE_NAME,
    date_format=DB_DATE_EXCHANGE_FORMAT_POSTGRES,
)

JINJASQL_FRAGMENT_AGGREGATED_GRID = Template(
    """
    SELECT COUNT(*), hexes.geom
                    FROM
                        ST_HexagonGrid(
                            {{ hex_size_meters }},
                            {% if grid_extent_viewport %}
                                ST_TileEnvelope({{ zoom }}, {{ x }}, {{ y }})
                            {% else %}
                                ST_SetSRID(ST_EstimatedExtent('$occurrences_table_name', '$occurrences_field_name_point'), 3857)
                            {% endif %} 
                        ) AS hexes
                    INNER JOIN ($jinjasql_fragment_filter_occurrences)
                    AS dashboard_filtered_occ

                    ON ST_Intersects(dashboard_filtered_occ.$occurrences_field_name_point, hexes.geom)
                    GROUP BY hexes.geom
"""
).substitute(
    occurrences_table_name=OCCURRENCES_TABLE_NAME,
    occurrences_field_name_point=OCCURRENCES_FIELD_NAME_POINT,
    jinjasql_fragment_filter_occurrences=JINJASQL_FRAGMENT_FILTER_OCCURRENCES,
)


def mvt_tiles_hexagon_grid_aggregated(request, zoom, x, y):
    """Tile server, showing occurrences aggregated by hexagon squares. Filters are honoured."""
    species_ids, datasets_ids, start_date, end_date = filters_from_request(request)

    sql_template = readable_string(
        Template(
            """
            WITH grid AS ($jinjasql_fragment_aggregated_grid),
                 mvtgeom AS (SELECT ST_AsMVTGeom(geom, ST_TileEnvelope({{ zoom }}, {{ x }}, {{ y }})) AS geom, count FROM grid)
            SELECT st_asmvt(mvtgeom.*) FROM mvtgeom;
    """
        ).substitute(
            jinjasql_fragment_aggregated_grid=JINJASQL_FRAGMENT_AGGREGATED_GRID
        )
    )

    sql_params = {
        # Map technicalities
        "hex_size_meters": ZOOM_TO_HEX_SIZE[zoom],
        "grid_extent_viewport": True,
        "zoom": zoom,
        "x": x,
        "y": y,
        # Filter included occurrences
        "species_ids": species_ids,
        "datasets_ids": datasets_ids,
    }

    # More occurrences filtering
    if start_date is not None:
        sql_params["start_date"] = start_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)
    if end_date is not None:
        sql_params["end_date"] = end_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)

    return HttpResponse(
        _mvt_query_data(sql_template, sql_params),
        content_type="application/vnd.mapbox-vector-tile",
    )


def occurrence_min_max_in_hex_grid_json(request):
    """Return the min, max occurrences count per hexagon, according to the zoom level. JSON format.

    This can be useful to dynamically color the grid according to the occurrence count
    """
    zoom = extract_int_request(request, "zoom")
    species_ids, datasets_ids, start_date, end_date = filters_from_request(request)

    sql_template = readable_string(
        Template(
            """
    WITH grid AS ($jinjasql_fragment_aggregated_grid)
    SELECT MIN(count), MAX(count) FROM grid;
    """
        ).substitute(
            jinjasql_fragment_aggregated_grid=JINJASQL_FRAGMENT_AGGREGATED_GRID
        )
    )

    sql_params = {
        "hex_size_meters": ZOOM_TO_HEX_SIZE[zoom],
        "grid_extent_viewport": False,
        "species_ids": species_ids,
        "datasets_ids": datasets_ids,
    }

    if start_date:
        sql_params["start_date"] = start_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)
    if end_date:
        sql_params["end_date"] = end_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)

    j = JinjaSql()
    query, bind_params = j.prepare_query(sql_template, sql_params)
    with connection.cursor() as cursor:
        cursor.execute(query, bind_params)
        r = cursor.fetchone()
        return JsonResponse({"min": r[0], "max": r[1]})


def _mvt_query_data(sql_template, sql_params):
    """Return binary data for the SQL query defined by sql_template and sql_params.
    Only for queries that returns a binary MVT (i.e. starts with "ST_AsMVT")"""
    j = JinjaSql()
    query, bind_params = j.prepare_query(sql_template, sql_params)
    with connection.cursor() as cursor:
        cursor.execute(query, bind_params)
        if cursor.rowcount != 0:
            data = cursor.fetchone()[0].tobytes()
        else:
            data = ""
        return data
