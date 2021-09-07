from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/species", views.species_list_json, name="api-species-list-json"),
    path(
        "api/tiles/hexagon-grid-aggregated/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles_hexagon_grid_aggregated,
        name="api-mvt-tiles-hexagon-grid-aggregated",
    ),
    path("api/min_max_per_hexagon", views.occurrence_min_max_in_hex_grid, name="api-mvt-min-max-per-hexagon")
]
