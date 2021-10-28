from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # Web pages
    path("", views.index_page, name="page-index"),
    path("about", views.about_page, name="page-about"),
    path(
        "occurrence/<int:pk>",
        views.occurrence_details_page,
        name="page-occurrence-details",
    ),
    path("signup", views.user_signup_page, name="page-signup"),
    # Api
    path("api/species", views.species_list_json, name="api-species-list-json"),
    path("api/datasets", views.datasets_list_json, name="api-datasets-list-json"),
    path(
        "api/filtered_occurrences/counter",
        views.filtered_occurrences_counter_json,
        name="api-filtered-occurrences-counter",
    ),
    path(
        "api/filtered_occurrences/monthly_histogram",
        views.filtered_occurrences_monthly_histogram_json,
        name="api-filtered-occurrences-monthly-histogram",
    ),
    path(
        "api/filtered_occurrences/data_page",
        views.filtered_occurrences_data_page_json,
        name="api-filtered-occurrences-data-page",
    ),
    # Maps
    path(
        "api/maps/tiles/hexagon_grid_aggregated/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_hexagon_grid_aggregated,
        name="api-mvt-tiles-hexagon-grid-aggregated",
    ),
    path(
        "api/maps/min_max_per_hexagon",
        views.occurrence_min_max_in_hex_grid_json,
        name="api-mvt-min-max-per-hexagon",
    ),
]
