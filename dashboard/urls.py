from django.urls import path, include

from . import views

app_name = "dashboard"

pages_urls = [
    path("", views.index_page, name="index"),
    path("about-site", views.about_site_page, name="about-site"),
    path("about-data", views.about_data_page, name="about-data"),
    path("whats-new", views.news_page, name="news"),
    path("alert/<int:alert_id>", views.alert_details_page, name="alert-details"),
    path("my-alerts", views.user_alerts_page, name="my-alerts"),
    path("new-alert", views.alert_create_page, name="alert-create"),
    path("edit-alert/<int:alert_id>", views.alert_edit_page, name="alert-edit"),
    path(
        "observation/<stable_id>",
        views.observation_details_page,
        name="observation-details",
    ),
    path("profile", views.user_profile_page, name="profile"),
    path("signup", views.user_signup_page, name="signup"),
    path("my-custom-areas", views.user_areas_page, name="my-custom-areas"),
]

maps_api_urls = [
    path(
        "min-max-per-hexagon",
        views.observation_min_max_in_hex_grid_json,
        name="mvt-min-max-per-hexagon",
    ),
    path(
        "tiles/observations/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_observations,
        name="mvt-tiles",
    ),
    path(
        "tiles/observations/hexagon-grid-aggregated/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_observations_hexagon_grid_aggregated,
        name="mvt-tiles-hexagon-grid-aggregated",
    ),
]

public_api_urls = [
    path("species", views.species_list_json, name="species-list-json"),
    path(
        "species-per-polygon",
        views.species_per_polygon_json,
        name="species-per-polygon-json",
    ),
    path(
        "wfs/observations", views.ObservationsWFSView.as_view(), name="wfs-observations"
    ),
]

internal_api_urls = [
    path(
        "alert/as-filters",
        views.alert_as_filters,
        name="alert-as-filters-json",
    ),
    path("alert", views.alert, name="alert"),
    path("area/<int:id>", views.area_geojson, name="area-geojson"),
    path("areas", views.areas_list_json, name="areas-list-json"),
    path(
        "available-alert-intervals",
        views.available_alert_intervals,
        name="available-alert-intervals",
    ),
    path("suggest-alert-name", views.suggest_alert_name, name="suggest-alert-name"),
    path("data-imports", views.dataimports_list_json, name="dataimports-list-json"),
    path("datasets", views.datasets_list_json, name="datasets-list-json"),
    path(
        "filtered-observations/counter",
        views.filtered_observations_counter_json,
        name="filtered-observations-counter",
    ),
    path(
        "filtered-observations/data_page",
        views.filtered_observations_data_page_json,
        name="filtered-observations-data-page",
    ),
    path(
        "filtered-observations/mark_as_seen",
        views.filtered_observations_mark_as_seen,
        name="filtered-observations-mark-as-seen",
    ),
    path(
        "filtered-observations/monthly_histogram",
        views.filtered_observations_monthly_histogram_json,
        name="filtered-observations-monthly-histogram",
    ),
    path(
        "maps/",
        include(
            (maps_api_urls, "maps"),
        ),
    ),
]

actions_urls = [
    path("delete_alert", views.delete_alert, name="delete-alert"),
    path(
        "mark-observation-as-unseen",
        views.mark_observation_as_unseen,
        name="mark-observation-as-unseen",
    ),
    path("delete-own-account", views.delete_own_account, name="delete-own-account"),
    path("area/delete/<int:id>", views.area_delete, name="area-delete"),
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
            (public_api_urls, "public-api"),
        ),
    ),
    path(
        "internal-api/",
        include(
            (internal_api_urls, "internal-api"),  # type: ignore
        ),
    ),
    path(
        "actions/",
        include(
            (actions_urls, "actions"),
        ),
    ),
]
