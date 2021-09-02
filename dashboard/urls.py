from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/species", views.species_list_json, name="api-species-list-json"),
    path(
        "api/tiles/<int:zoom>/<int:x>/<int:y>.mvt",
        views.mvt_tiles,
        name="api-mvt-tiles",
    ),
]
