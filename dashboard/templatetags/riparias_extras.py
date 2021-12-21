import json

from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe


register = template.Library()


@register.simple_tag(takes_context=True)
def js_config_object(context):
    # When adding stuff here, don't forget to update the corresponding TypeScript interface in assets/ts/interfaces.ts
    conf = {
        "currentLanguageCode": context.request.LANGUAGE_CODE,  # for the example (not used yet, delete later?)
        "targetCountryCode": settings.RIPARIAS[
            "TARGET_COUNTRY_CODE"
        ],  # for the example (not used yet, delete later?)
        "apiEndpoints": {
            "speciesListUrl": reverse("dashboard:api-species-list-json"),
            "datasetsListUrl": reverse("dashboard:api-datasets-list-json"),
            "areasListUrl": reverse("dashboard:api-areas-list-json"),
            "observationsCounterUrl": reverse(
                "dashboard:api-filtered-observations-counter"
            ),
            "observationsJsonUrl": reverse(
                "dashboard:api-filtered-observations-data-page"
            ),
            "tileServerUrlTemplate": reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 1, "x": 2, "y": 3},
            )
            .replace("1", "{z}")
            .replace("2", "{x}")
            .replace("3", "{y}"),
            "observationDetailsUrlTemplate": reverse(
                "dashboard:page-observation-details", kwargs={"stable_id": 1}
            ).replace("1", "{stable_id}"),
            "areasUrlTemplate": reverse(
                "dashboard:api-area-geojson", kwargs={"id": 1}
            ).replace("1", "{id}"),
            "minMaxOccPerHexagonUrl": reverse("dashboard:api-mvt-min-max-per-hexagon"),
            "observationsHistogramDataUrl": reverse(
                "dashboard:api-filtered-observations-monthly-histogram"
            ),
        },
    }
    return mark_safe(json.dumps(conf))


@register.filter
def gbif_download_url(value):
    return f"https://www.gbif.org/occurrence/download/{value}"


@register.filter
def gbif_occurrence_url(value):
    return f"https://www.gbif.org/occurrence/{value}"
