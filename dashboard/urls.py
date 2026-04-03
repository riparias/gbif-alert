from django.urls import path, include

from . import views

app_name = "dashboard"

pages_urls = [
    path("", views.index_page, name="index"),
    path("experiment/", views.index_page, name="experiment"),
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
]

internal_api_urls = [
    path(
        "maps/",
        include(
            (maps_api_urls, "maps"),
        ),
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
            (public_api_urls, "public-api"),
        ),
    ),
    path(
        "internal-api/",
        include(
            (internal_api_urls, "internal-api"),  # type: ignore
        ),
    ),
]
