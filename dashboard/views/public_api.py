"""Public-facing API views"""
from django.contrib.gis.geos import GEOSGeometry
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse, HttpRequest
from gisserver.features import FeatureType, field  # type: ignore
from gisserver.types import XsdElement, XsdTypes  # type: ignore
from gisserver.views import WFSView  # type: ignore

from dashboard.models import Species, DATA_SRID, Observation
from dashboard.views.helpers import (
    model_to_json_list,
    filtered_observations_from_request,
    extract_int_request,
)


def filtered_observations_counter_json(request: HttpRequest) -> JsonResponse:
    """Count the observations according to the filters received

    See `internal_api.py`'s docstring for the observations filtering.

    parameters:
    - filters: same format than other endpoints: getting observations, map tiles, ...
    """
    qs = filtered_observations_from_request(request)
    return JsonResponse({"count": qs.count()})


def filtered_observations_data_page_json(request: HttpRequest) -> JsonResponse:
    """Main endpoint to get paginated observations (data tables, ...)

    parameters:
    - filters: same format than other endpoints: getting observations, map tiles, ... (See `internal_api.py`'s docstring)
    - order: optional, observations order (passed to QuerySet.order_by)
    - mode: "normal" | "short". Defaults to normal. If short, only the most important fields are returned
    - limit: number of observations per page
    - page_number: requested page number

    response example (normal mode):

    {
      "results": [
        {
          "id": 1130128,
          "stableId": "58b86259157a6c9bd98f6fc8025bc51a796fdf7d",
          "gbifId": "4399020308",
          "lat": 50.62886099999997,
          "lon": 4.453551,
          "scientificName": "Vespa Velutina",
          "vernacularName": "",
          "datasetName": "DEMNA-DNE : Early warning system on Introduced Species in Wallonia",
          "date": "2023-08-21",
          "seenByCurrentUser": false
        },
        {
          "id": 1130129,
          "stableId": "c3356897d006583b8f22a3c5c655a54a348079d7",
          "gbifId": "4399020310",
          "lat": 50.61108599999998,
          "lon": 5.579655,
          "scientificName": "Vespa Velutina",
          "vernacularName": "",
          "datasetName": "DEMNA-DNE : Early warning system on Introduced Species in Wallonia",
          "date": "2023-08-21",
          "seenByCurrentUser": false
        },
        {
          "id": 1130144,
          "stableId": "873fb841920d13d9d55f1714bdccb7fa518c28e7",
          "gbifId": "4399020302",
          "lat": 50.667837999999996,
          "lon": 5.471714,
          "scientificName": "Vespa Velutina",
          "vernacularName": "",
          "datasetName": "DEMNA-DNE : Early warning system on Introduced Species in Wallonia",
          "date": "2023-08-21",
          "seenByCurrentUser": false
        }
      ],
      "pageNumber": 1,
      "firstPage": 1,
      "lastPage": 44436,
      "totalResultsCount": 133306
    }

    Notes:
        - If the page number is negative or greater than the number of pages, it returns the last page.
        - If no results are returned because of the filtering: totalResultsCount == 0 and results == []
    """

    order = request.GET.get("order")
    limit = extract_int_request(request, "limit")
    mode = request.GET.get("mode", "normal")
    if limit is None:
        limit = 50
    page_number = extract_int_request(request, "page_number")

    observations = filtered_observations_from_request(request)
    if order is not None:
        observations = observations.order_by(order)

    paginator = Paginator(observations, limit)

    page = paginator.get_page(page_number)

    if mode == "normal":
        results = [obs.as_dict(for_user=request.user) for obs in page.object_list]
    elif mode == "short":
        results = [obs.as_short_dict() for obs in page.object_list]

    return JsonResponse(
        {
            "results": results,
            "pageNumber": page.number,  # Number of the current page
            "firstPage": page.paginator.page_range.start,
            # page_range is a python range, (last element not included!)
            "lastPage": page.paginator.page_range.stop - 1,
            "totalResultsCount": page.paginator.count,
        }
    )


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


class CustomXsdElementVernacularNameNL(XSDElementForceStringType):
    def get_value(self, instance):
        return instance.species.vernacular_name_nl


class CustomXsdElementVernacularNameEN(XSDElementForceStringType):
    def get_value(self, instance):
        return instance.species.vernacular_name_en


class CustomXsdElementVernacularNameFR(XSDElementForceStringType):
    def get_value(self, instance):
        return instance.species.vernacular_name_fr


class CustomXsdElementDatasetName(XSDElementForceStringType):
    def get_value(self, instance):
        return instance.source_dataset.name


class CustomXsdElementDataSetGBIFKey(XSDElementForceStringType):
    def get_value(self, instance):
        return instance.source_dataset.gbif_dataset_key


class ObservationsWFSView(WFSView):
    feature_types = [
        FeatureType(
            Observation.objects.all(),
            fields=[
                "location",
                "gbif_id",
                "stable_id",
                "species_id",
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
                field(
                    "species_vernacular_name_nl",
                    model_attribute="species",
                    xsd_class=CustomXsdElementVernacularNameNL,
                ),
                field(
                    "species_vernacular_name_en",
                    model_attribute="species",
                    xsd_class=CustomXsdElementVernacularNameEN,
                ),
                field(
                    "species_vernacular_name_fr",
                    model_attribute="species",
                    xsd_class=CustomXsdElementVernacularNameFR,
                ),
                field(
                    "dataset_name",
                    model_attribute="source_dataset",
                    xsd_class=CustomXsdElementDatasetName,
                ),
                field(
                    "dataset_gbif_key",
                    model_attribute="source_dataset",
                    xsd_class=CustomXsdElementDataSetGBIFKey,
                ),
                field("observation_date", model_attribute="date"),
                "individual_count",
                "locality",
                "municipality",
                "basis_of_record",
                "recorded_by",
                "coordinate_uncertainty_in_meters",
                "references",
            ],
        ),
    ]
