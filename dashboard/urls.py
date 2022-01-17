from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # Web pages
    path("", views.index_page, name="page-index"),
    path("about", views.about_page, name="page-about"),
    path(
        "observation/<stable_id>",
        views.observation_details_page,
        name="page-observation-details",
    ),
    path("signup", views.user_signup_page, name="page-signup"),
    path("profile", views.user_profile_page, name="page-profile"),
    path("my-alerts", views.user_alerts_page, name="page-my-alerts"),
    path("alert/<int:alert_id>", views.alert_details_page, name="page-alert-details"),
    path("new-alert", views.alert_create_page, name="page-alert-create"),
    path("delete-alert", views.action_alert_delete, name="action-alert-delete"),
    path(
        "mark_observation_as_not_viewed",
        views.mark_observation_as_not_viewed,
        name="page-mark-observation-as-not-viewed",
    ),
    # Api
    path("api/species", views.species_list_json, name="api-species-list-json"),
    path("api/datasets", views.datasets_list_json, name="api-datasets-list-json"),
    path(
        "api/filtered_observations/counter",
        views.filtered_observations_counter_json,
        name="api-filtered-observations-counter",
    ),
    path(
        "api/filtered_observations/monthly_histogram",
        views.filtered_observations_monthly_histogram_json,
        name="api-filtered-observations-monthly-histogram",
    ),
    path(
        "api/filtered_observations/data_page",
        views.filtered_observations_data_page_json,
        name="api-filtered-observations-data-page",
    ),
    path("api/areas", views.areas_list_json, name="api-areas-list-json"),
    path("api/area/<int:id>", views.area_geojson, name="api-area-geojson"),
    # Maps
    path(
        "api/maps/tiles/hexagon_grid_aggregated/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_hexagon_grid_aggregated,
        name="api-mvt-tiles-hexagon-grid-aggregated",
    ),
    path(
        "api/maps/min_max_per_hexagon",
        views.observation_min_max_in_hex_grid_json,
        name="api-mvt-min-max-per-hexagon",
    ),
]
