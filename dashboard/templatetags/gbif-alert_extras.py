import json
import re
from typing import Any
from urllib.parse import urlencode

from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe

from dashboard.models import DataImport

register = template.Library()


def _my_reverse(view_name, kwargs=None, query_kwargs=None):
    """
    Custom reverse to add a query string after the url
    Example usage:
    url = my_reverse('my_test_url', kwargs={'pk': object.id}, query_kwargs={'next': reverse('home')})
    """
    url = reverse(view_name, kwargs=kwargs)

    if query_kwargs:
        return f"{url}?{urlencode(query_kwargs)}"

    return url


def _build_dashboard_url_with_filter(k: str, v: Any) -> str:
    return _my_reverse(
        "dashboard:pages:index",
        query_kwargs={"filters": {k: v}},
    )


def _build_mvt_url_template(url_pattern: str) -> str:
    return (
        reverse(url_pattern, kwargs={"zoom": 1, "x": 2, "y": 3})
        .replace("1", "{z}")
        .replace("2", "{x}")
        .replace("3", "{y}")
    )


@register.simple_tag
def dashboard_url_filtered_by_data_import(data_import: DataImport) -> str:
    return _build_dashboard_url_with_filter(
        k="initialDataImportIds", v=[data_import.pk]
    )


@register.simple_tag(takes_context=True)
def js_config_object(context):
    # When adding stuff here, don't forget to update the corresponding TypeScript interface in assets/ts/interfaces.ts
    observation_details_url_template = reverse(
        "dashboard:pages:observation-details", kwargs={"stable_id": 1}
    ).replace("1", "{stable_id}")
    observation_details_url_template_with_origin = (
        f"{observation_details_url_template}?origin={{origin}}"
    )

    conf = {
        "authenticatedUser": context.request.user.is_authenticated,
        "apiEndpoints": {
            "speciesListUrl": reverse("dashboard:public-api:species-list-json"),
            "datasetsListUrl": reverse("dashboard:internal-api:datasets-list-json"),
            "areasListUrl": reverse("dashboard:internal-api:areas-list-json"),
            "dataImportsListUrl": reverse(
                "dashboard:internal-api:dataimports-list-json"
            ),
            "observationsCounterUrl": reverse(
                "dashboard:internal-api:filtered-observations-counter"
            ),
            "observationsJsonUrl": reverse(
                "dashboard:internal-api:filtered-observations-data-page"
            ),
            "markObservationsAsSeenUrl": reverse(
                "dashboard:internal-api:filtered-observations-mark-as-seen"
            ),
            "tileServerAggregatedUrlTemplate": _build_mvt_url_template(
                "dashboard:internal-api:maps:mvt-tiles-hexagon-grid-aggregated"
            ),
            "tileServerUrlTemplate": _build_mvt_url_template(
                "dashboard:internal-api:maps:mvt-tiles"
            ),
            "observationDetailsUrlTemplate": observation_details_url_template_with_origin,
            "myCustomAreasUrl": reverse(
                "dashboard:pages:my-custom-areas"
            ),  # TODO: some entries are not API endpoints, but regular pages URLs. Maybe we should have a separate object for those? OR just rename this "apiEndpoints" to "urls"?
            "areasUrlTemplate": reverse(
                "dashboard:internal-api:area-geojson", kwargs={"id": 1}
            ).replace("1", "{id}"),
            "areaDeleteUrlTemplate": reverse(
                "dashboard:actions:area-delete", kwargs={"id": 1}
            ).replace("1", "{id}"),
            "minMaxOccPerHexagonUrl": reverse(
                "dashboard:internal-api:maps:mvt-min-max-per-hexagon"
            ),
            "observationsHistogramDataUrl": reverse(
                "dashboard:internal-api:filtered-observations-monthly-histogram"
            ),
            "alertAsFiltersUrl": reverse(
                "dashboard:internal-api:alert-as-filters-json"
            ),
            "alertPageUrlTemplate": reverse(
                "dashboard:pages:alert-details", kwargs={"alert_id": 1}
            ).replace("1", "{id}"),
        },
        "mainMapConfig": settings.GBIF_ALERT["MAIN_MAP_CONFIG"],
    }
    if context.request.user.is_authenticated:
        conf["userId"] = context.request.user.pk

    return mark_safe(json.dumps(conf))


@register.filter
def gbif_download_url(value):
    return f"https://www.gbif.org/occurrence/download/{value}"


@register.filter
def gbif_occurrence_url(occurrence_id: str) -> str:
    return f"https://www.gbif.org/occurrence/{occurrence_id}"


@register.filter
def gbif_dataset_url(dataset_key: str) -> str:
    return f"https://www.gbif.org/dataset/{dataset_key}"


def _is_url(s: str) -> bool:
    regex_url = re.compile(
        r"^(?:http|ftp)s?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return re.match(regex_url, s) is not None


@register.filter
def as_link_if_url(value):
    if _is_url(value):
        return mark_safe(f'<a href="{value}">{value}</a>')
    else:
        return value
