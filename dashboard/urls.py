from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # Standard pages
    path("", views.index, name="index"),
    path("about", views.about, name="about"),
    path("occurrence/<int:pk>", views.occurrence_details, name="occurrence-details"),
    # Apis
    path("api/species", views.species_list_json, name="api-species-list-json"),
    path("api/datasets", views.datasets_list_json, name="api-datasets-list-json"),
    path(
        "api/occurrences_count",
        views.occurrences_counter,
        name="api-occurrences-counter",
    ),
    path(
        "api/occurrences_monthly_histogram",
        views.occurrences_monthly_histogram_json,
        name="api-occurrences-monthly-histogram",
    ),
    path("api/occurrences_json", views.occurrences_json, name="api-occurrences-json"),
    # Maps
    path(
        "api/tiles/hexagon-grid-aggregated/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_hexagon_grid_aggregated,
        name="api-mvt-tiles-hexagon-grid-aggregated",
    ),
    path(
        "api/min_max_per_hexagon",
        views.occurrence_min_max_in_hex_grid,
        name="api-mvt-min-max-per-hexagon",
    ),
]
