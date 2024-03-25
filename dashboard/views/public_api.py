"""Public-facing API views"""
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Count
from django.http import JsonResponse, HttpRequest
from gisserver.features import FeatureType, field  # type: ignore
from gisserver.geometries import CRS  # type: ignore
from gisserver.views import WFSView  # type: ignore

from dashboard.models import Species, DATA_SRID, Observation
from dashboard.views.helpers import model_to_json_list


def species_list_json(_) -> JsonResponse:
    """A list of all species known to the system, in JSON format

    Order: undetermined
    """
    return model_to_json_list(Species)


def species_per_polygon_json(request: HttpRequest) -> JsonResponse:
    """An object with species details and observations counter, for each species that occurs in the given polygon

    Method: GET

    Params:
        p: the polygon as a URL-encoded Well-know text string (EPSG:4326)

    Sample output:
    [
        {
        "id": 1,
        "scientificName": "Elodea nuttallii",
        "vernacularName": "",
        "gbifTaxonKey": 5329212,
        "groupCode": "PL",
        "observationCountInPolygon": 1
        },
        ...
    ]
    """
    feature = GEOSGeometry(request.GET.get("p"), srid=4326)

    annotated_species = Species.objects.filter(
        observation__location__within=feature.transform(DATA_SRID, clone=True)
    ).annotate(num_observations=Count("observation"))

    r = []
    for entry in annotated_species:
        d = entry.as_dict
        d["observationCountInPolygon"] = entry.num_observations
        r.append(d)

    return JsonResponse(r, safe=False)


class ObservationsWFSView(WFSView):
    feature_types = [
        FeatureType(
            Observation.objects.all(),
            fields=[
                "gbif_id",
                # field("data_provider_occurrence_id", model_attribute="occurrence_id"),
                "stable_id",
                # field("species-id", model_attribute="species_id"),
                # ".species.name",
                field("species-name", model_attribute="species.name"),
                # field(
                #     "species",
                #     fields=[
                #         "id",
                #         "name",
                #         "vernacular_name_nl",
                #         "vernacular_name_en",
                #         "vernacular_name_fr",
                #     ],
                # ),
                field(
                    "dataset",
                    fields=[
                        "name",
                        "gbif_dataset_key",
                    ],
                    model_attribute="source_dataset",
                ),
                "location",
                field("observation_date", model_attribute="date"),
                "individual_count",
                "locality",
                "municipality",
                "basis_of_record",
                "recorded_by",
                "coordinate_uncertainty_in_meters",
                "references",
            ],
            other_crs=[CRS.from_srid(31370)],
        ),
    ]
