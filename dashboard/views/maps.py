"""Observations tile server + related endpoints"""

from string import Template

from django.db import connection
from django.http import HttpResponse, JsonResponse, HttpRequest
from jinjasql import JinjaSql

from dashboard.models import Observation, Area, ObservationView, Species
from dashboard.utils import readable_string
from dashboard.views.helpers import filters_from_request, extract_int_request
from django.conf import settings

AREAS_TABLE_NAME = Area.objects.model._meta.db_table
OBSERVATIONS_TABLE_NAME = Observation.objects.model._meta.db_table
OBSERVATIONVIEWS_TABLE_NAME = ObservationView.objects.model._meta.db_table
SPECIES_TABLE_NAME = Species.objects.model._meta.db_table

OBSERVATIONS_FIELD_NAME_POINT = "location"

# ! Make sure the following formats are in sync
DB_DATE_EXCHANGE_FORMAT_PYTHON = "%Y-%m-%d"  # To be passed to strftime()
DB_DATE_EXCHANGE_FORMAT_POSTGRES = "YYYY-MM-DD"  # To be used in SQL queries


# !! IMPORTANT !! Make sure the observation filtering here is equivalent to what's done in
# other places (views.helpers.filtered_observations_from_request). Otherwise, observations returned on the map and on
# other components (table, ...) will be inconsistent.
WHERE_CLAUSE = readable_string(
    Template(
        """ 
        1 = 1
        {% if species_ids %}
            AND obs.species_id IN {{ species_ids | inclause }}
        {% endif %}
        {% if datasets_ids %}
            AND obs.source_dataset_id IN {{ datasets_ids | inclause }}
        {% endif %}
        {% if start_date %}
            AND obs.date >= TO_DATE({{ start_date }}, '$date_format')
        {% endif %}
        {% if end_date %}
            AND obs.date <= TO_DATE({{ end_date }}, '$date_format')
        {% endif %}
        {% if area_ids %}
            AND ST_Within(obs.location, areas.mpoly)
        {% endif %}
        {% if initial_data_import_ids %}
            AND obs.initial_data_import_id IN {{ initial_data_import_ids | inclause }}
        {% endif %}
        {% if status == 'unseen' %}
            AND NOT (EXISTS(
            SELECT (1) FROM $observationview_table_name ov WHERE (
                ov.id IN (SELECT ov1.id FROM $observationview_table_name ov1 WHERE ov1.user_id = {{ user_id }}) 
                AND ov.observation_id = obs.id
            ) LIMIT 1))
        {% endif %}
        {% if status == 'seen' %}
            AND $observationview_table_name.id IN (
                SELECT ov1.id FROM $observationview_table_name ov1 WHERE ov1.user_id = {{ user_id }}
            )
        {% endif %}
"""
    ).substitute(
        observationview_table_name=OBSERVATIONVIEWS_TABLE_NAME,
        date_format=DB_DATE_EXCHANGE_FORMAT_POSTGRES,
    )
)

JINJASQL_FRAGMENT_FILTER_OBSERVATIONS = Template(
    """
    SELECT * FROM $observations_table_name as obs
    LEFT JOIN $species_table_name as species
    ON obs.species_id = species.id
    {% if status == 'seen' %}
        INNER JOIN $observationview_table_name
        ON obs.id = $observationview_table_name.observation_id
    {% endif %}
    
    {% if area_ids %}
    , (SELECT mpoly FROM $areas_table_name WHERE $areas_table_name.id IN {{ area_ids | inclause }}) AS areas
    {% endif %}
    WHERE (
        $where_clause
    )
"""
).substitute(
    observationview_table_name=OBSERVATIONVIEWS_TABLE_NAME,
    areas_table_name=AREAS_TABLE_NAME,
    species_table_name=SPECIES_TABLE_NAME,
    observations_table_name=OBSERVATIONS_TABLE_NAME,
    where_clause=WHERE_CLAUSE,
)

JINJASQL_FRAGMENT_AGGREGATED_GRID = Template(
    """
    SELECT COUNT(*), hexes.geom
    FROM
        ST_HexagonGrid({{ hex_size_meters }}, ST_TileEnvelope({{ zoom }}, {{ x }}, {{ y }})) AS hexes
        INNER JOIN ($jinjasql_fragment_filter_observations)
    AS dashboard_filtered_occ

    ON ST_Intersects(dashboard_filtered_occ.$observations_field_name_point, hexes.geom)
    GROUP BY hexes.geom
"""
).substitute(
    observations_table_name=OBSERVATIONS_TABLE_NAME,
    observations_field_name_point=OBSERVATIONS_FIELD_NAME_POINT,
    jinjasql_fragment_filter_observations=JINJASQL_FRAGMENT_FILTER_OBSERVATIONS,
)


def mvt_tiles_observations(
    request: HttpRequest, zoom: int, x: int, y: int
) -> HttpResponse:
    """Tile server, showing non-aggregated observations. Filters are honoured."""
    sql_template = readable_string(
        Template(
            """
            WITH mvtgeom AS (
                SELECT ST_AsMVTGeom(observations.location, ST_TileEnvelope({{ zoom }}, {{ x }}, {{ y }})), observations.gbif_id, observations.stable_id, observations.name AS scientific_name
                FROM ($jinjasql_filtered_observations) AS observations
            )
            SELECT st_asmvt(mvtgeom.*) FROM mvtgeom;
    """
        ).substitute(
            jinjasql_filtered_observations=JINJASQL_FRAGMENT_FILTER_OBSERVATIONS
        )
    )

    (
        species_ids,
        datasets_ids,
        start_date,
        end_date,
        area_ids,
        status_for_user,
        initial_data_import_ids,
    ) = filters_from_request(request)

    sql_params = {
        # Map technicalities
        "zoom": zoom,
        "x": x,
        "y": y,
        # Filter included observations
        "species_ids": species_ids,
        "datasets_ids": datasets_ids,
        "area_ids": area_ids,
        "initial_data_import_ids": initial_data_import_ids,
    }

    if status_for_user and request.user.is_authenticated:
        sql_params["status"] = status_for_user
        sql_params["user_id"] = request.user.pk

    # More observations filtering
    if start_date is not None:
        sql_params["start_date"] = start_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)
    if end_date is not None:
        sql_params["end_date"] = end_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)

    return HttpResponse(
        _mvt_query_data(sql_template, sql_params),
        content_type="application/vnd.mapbox-vector-tile",
    )


def mvt_tiles_observations_hexagon_grid_aggregated(
    request: HttpRequest, zoom: int, x: int, y: int
) -> HttpResponse:
    """Tile server, showing observations aggregated by hexagon squares. Filters are honoured."""
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

    (
        species_ids,
        datasets_ids,
        start_date,
        end_date,
        area_ids,
        status_for_user,
        initial_data_import_ids,
    ) = filters_from_request(request)

    sql_params = {
        # Map technicalities
        "hex_size_meters": settings.ZOOM_TO_HEX_SIZE[zoom],
        "zoom": zoom,
        "x": x,
        "y": y,
        # Filter included observations
        "species_ids": species_ids,
        "datasets_ids": datasets_ids,
        "area_ids": area_ids,
        "initial_data_import_ids": initial_data_import_ids,
    }

    if status_for_user and request.user.is_authenticated:
        sql_params["status"] = status_for_user
        sql_params["user_id"] = request.user.pk

    # More observations filtering
    if start_date is not None:
        sql_params["start_date"] = start_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)
    if end_date is not None:
        sql_params["end_date"] = end_date.strftime(DB_DATE_EXCHANGE_FORMAT_PYTHON)

    return HttpResponse(
        _mvt_query_data(sql_template, sql_params),
        content_type="application/vnd.mapbox-vector-tile",
    )


def observation_min_max_in_hex_grid_json(request: HttpRequest):
    """Return the min, max observations count per hexagon, according to the zoom level. JSON format.

    This can be useful to dynamically color the grid according to the count
    """
    zoom = extract_int_request(request, "zoom")
    if zoom is not None:
        (
            species_ids,
            datasets_ids,
            start_date,
            end_date,
            area_ids,
            status_for_user,
            initial_data_import_ids,
        ) = filters_from_request(request)

        sql_template = readable_string(
            Template(
                """
                WITH grid AS (
                    SELECT COUNT(*)
                    FROM (SELECT * FROM hexa_$hex_size_meters) AS obs
                        LEFT JOIN dashboard_species as species ON obs.species_id = species.id
                        
                        {% if area_ids %}
                        ,(SELECT mpoly FROM $areas_table_name WHERE $areas_table_name.id IN {{ area_ids | inclause }}) AS areas
                        {% endif %}
                        {% if status == 'seen' %}
                            INNER JOIN $observationview_table_name
                            ON obs.id = $observationview_table_name.observation_id
                        {% endif %}
                    WHERE (
                        $where_clause
                    )      
                GROUP BY obs.geom
                )
                
                SELECT MIN(count), MAX(count) FROM grid;
                """
            ).substitute(
                hex_size_meters=settings.ZOOM_TO_HEX_SIZE[zoom],
                areas_table_name=AREAS_TABLE_NAME,
                observationview_table_name=OBSERVATIONVIEWS_TABLE_NAME,
                where_clause=WHERE_CLAUSE,
            )
        )

        sql_params = {
            "species_ids": species_ids,
            "datasets_ids": datasets_ids,
            "area_ids": area_ids,
            "initial_data_import_ids": initial_data_import_ids,
        }

        if status_for_user and request.user.is_authenticated:
            sql_params["status"] = status_for_user
            sql_params["user_id"] = request.user.pk

        if start_date:
            sql_params["start_date"] = start_date.strftime(
                DB_DATE_EXCHANGE_FORMAT_PYTHON
            )
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
