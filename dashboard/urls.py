from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),

    path('api/species', views.species_list_json, name='api-species-list-json')
]