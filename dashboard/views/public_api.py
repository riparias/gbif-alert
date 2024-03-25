"""Public-facing API views"""
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Count
from django.http import JsonResponse, HttpRequest
from gisserver.features import FeatureType, field  # type: ignore
from gisserver.types import XsdElement, XsdTypes
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


# Unfortunately I can't make the  "flattened feature" approach of django-gisserver to
# work, so I have to define custom classes for all the "complex" fields I want to expose
# I also have to override the type in the constructor if it ius not an integer otherwise
# the metadata will be incorrect and values will appear as NULL in QGIS, for example.
# Beware: the interactions with model_attributes is quite messy and not well documented
# in the django-gisserver documentation. This is ugly, but this is the only way I found.
class XSDElementForceStringType(XsdElement):
    """Custom helper to force a string type in the XSD metadata"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = XsdTypes.string


class CustomXsdElementGBIFTaxonKey(XsdElement):
    def get_value(self, instance):
        return instance.species.gbif_taxon_key


class CustomXsdElementScientificName(XSDElementForceStringType):
    def get_value(self, instance):
        return instance.species.name


class ObservationsWFSView(WFSView):
    feature_types = [
        FeatureType(
            Observation.objects.filter(coordinate_uncertainty_in_meters__lt=5),
            # fields=[
            #     "gbif_id",
            #     "stable_id",
            #     # field("species-scientific-name", model_attribute="species.name"),
            #     # field("species_id", model_attribute="species.id"),
            #     field(
            #         # "species.vernacular_name_nl",
            #         "species-vernacular-name-nl",
            #         model_attribute="observation.species.vernacular_name_nl",
            #     ),
            #     # field(
            #     #     "species-vernacular-name-en",
            #     #     model_attribute="species.vernacular_name_en",
            #     # ),
            #     # field(
            #     #     "species-vernacular-name-fr",
            #     #     model_attribute="species.vernacular_name_fr",
            #     # ),
            #     # field("dataset-name", model_attribute="source_dataset.name"),
            #     # field(
            #     #     "dataset-gbif-key",
            #     #     model_attribute="source_dataset.gbif_dataset_key",
            #     # ),
            #     "location",
            #     field("observation_date", model_attribute="date"),
            #     "individual_count",
            #     "locality",
            #     "municipality",
            #     "basis_of_record",
            #     "recorded_by",
            #     "coordinate_uncertainty_in_meters",
            #     "references",
            # ],
            fields=[
                "location",
                "gbif_id",
                "stable_id",
                field(
                    "species_gbif_key",
                    model_attribute="species",
                    xsd_class=CustomXsdElementGBIFTaxonKey,
                ),
                field(
                    "species_scientific_name",
                    model_attribute="species",
                    xsd_class=CustomXsdElementScientificName,
                ),
            ],
        ),
    ]
