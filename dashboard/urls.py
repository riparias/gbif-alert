from django.urls import path, include

from . import views

app_name = "dashboard"

pages_urls = [
    path("", views.index_page, name="index"),
    path("about", views.about_page, name="about"),
    path("alert/<int:alert_id>", views.alert_details_page, name="alert-details"),
    path("my_alerts", views.user_alerts_page, name="my-alerts"),
    path("new_alert", views.alert_create_page, name="alert-create"),
    path(
        "observation/<stable_id>",
        views.observation_details_page,
        name="observation-details",
    ),
    path("profile", views.user_profile_page, name="profile"),
    path("signup", views.user_signup_page, name="signup"),
]

maps_api_urls = [
    path(
        "min_max_per_hexagon",
        views.observation_min_max_in_hex_grid_json,
        name="mvt-min-max-per-hexagon",
    ),
    path(
        "tiles/observations/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_observations,
        name="mvt-tiles",
    ),
    path(
        "tiles/observations/hexagon_grid_aggregated/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_observations_hexagon_grid_aggregated,
        name="mvt-tiles-hexagon-grid-aggregated",
    ),
]

api_urls = [
    path("areas", views.areas_list_json, name="areas-list-json"),
    path(
        "alert/as_filters",
        views.alert_as_filters,
        name="alert-as-filters-json",
    ),
    path("dataimports", views.dataimports_list_json, name="dataimports-list-json"),
    path("datasets", views.datasets_list_json, name="datasets-list-json"),
    path(
        "filtered_observations/counter",
        views.filtered_observations_counter_json,
        name="filtered-observations-counter",
    ),
    path(
        "filtered_observations/data_page",
        views.filtered_observations_data_page_json,
        name="filtered-observations-data-page",
    ),
    path(
        "filtered_observations/monthly_histogram",
        views.filtered_observations_monthly_histogram_json,
        name="filtered-observations-monthly-histogram",
    ),
    path(
        "maps",
        include(
            (maps_api_urls, "maps"),
        ),
    ),
    path("species", views.species_list_json, name="species-list-json"),
    path("area/<int:id>", views.area_geojson, name="area-geojson"),
]

actions_urls = [
    path("delete_alert", views.delete_alert, name="delete-alert"),
    path(
        "mark_observation_as_unseen",
        views.mark_observation_as_unseen,
        name="mark-observation-as-unseen",
    ),
]

urlpatterns = [
    path(
        "",
        include(
            (pages_urls, "pages"),
        ),
    ),
    path(
        "api/",
        include(
            (api_urls, "api"),
        ),
    ),
    path(
        "actions/",
        include(
            (actions_urls, "actions"),
        ),
    ),
]
