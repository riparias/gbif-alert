import json

from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def js_config_object(context):
    conf = {
        "currentLanguageCode": context.request.LANGUAGE_CODE,  # for the example (not used yet, delete later?)
        "targetCountryCode": settings.RIPARIAS[
            "TARGET_COUNTRY_CODE"
        ],  # for the example (not used yet, delete later?)
        "apiEndpoints": {
            "tileServerUrlTemplate": reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 1, "x": 2, "y": 3}
            )
            .replace("1", "{z}")
            .replace("2", "{x}")
            .replace("3", "{y}"),
            "minMaxOccPerHexagonUrl": reverse("dashboard:api-mvt-min-max-per-hexagon")
        },
    }
    return mark_safe(json.dumps(conf))
