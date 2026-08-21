import json
import re

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, get_language_info

from dashboard.models import Area

register = template.Library()


def _build_mvt_url_template(url_pattern: str) -> str:
    return (
        reverse(url_pattern, kwargs={"zoom": 1, "x": 2, "y": 3})
        .replace("1", "{z}")
        .replace("2", "{x}")
        .replace("3", "{y}")
    )


SPECIES_NAME_MODE_COOKIE = "gbif-alert.species-name-display"
SPECIES_NAME_MODES = {"scientific", "vernacular"}
SPECIES_NAME_MODE_DEFAULT = "scientific"


@register.simple_tag(takes_context=True)
def nav_config_json(context):
    """Serialize all data the Vue navbar needs into a JSON string.

    Injected into the page as a <script type="application/json"> element so that
    the Vue app can read it synchronously at mount time without a fetch round-trip.
    """
    user = context.request.user

    raw_mode = context.request.COOKIES.get(SPECIES_NAME_MODE_COOKIE, "")
    species_name_mode = (
        raw_mode if raw_mode in SPECIES_NAME_MODES else SPECIES_NAME_MODE_DEFAULT
    )

    enabled_languages = [
        {"code": code, "nameLocal": get_language_info(code)["name_local"]}
        for code in settings.GBIF_ALERT["ENABLED_LANGUAGES"]
    ]

    conf = {
        "siteName": settings.GBIF_ALERT["SITE_NAME"],
        "primaryPalette": settings.GBIF_ALERT.get("PRIMEVUE_PRIMARY_PALETTE", "indigo"),
        "currentLanguage": get_language(),
        "enabledLanguages": enabled_languages,
        "user": {
            "isAuthenticated": user.is_authenticated,
            "username": user.username if user.is_authenticated else None,
            "isSuperuser": user.is_superuser if user.is_authenticated else False,
            "hasUnseenNews": user.has_unseen_news if user.is_authenticated else False,
            "hasAlertsWithUnseenObservations": (
                user.has_alerts_with_unseen_observations
                if user.is_authenticated
                else False
            ),
        },
        "urls": {
            "index": reverse("dashboard:pages:index"),
            "news": reverse("dashboard:pages:news"),
            "myAlerts": reverse("dashboard:pages:my-alerts"),
            "aboutSite": reverse("dashboard:pages:about-site"),
            "aboutData": reverse("dashboard:pages:about-data"),
            "profile": reverse("dashboard:pages:profile"),
            "passwordChange": reverse("password_change"),
            "myCustomAreas": reverse("dashboard:pages:my-custom-areas"),
            "signin": reverse("signin"),
            "signup": reverse("dashboard:pages:signup"),
            "admin": reverse("admin:index"),
            "setLanguage": reverse("set_language"),
        },
        # Map configuration: initial viewport and tile/API endpoint URL templates.
        # Used by ObservationsMap.vue to initialise the map without a fetch round-trip.
        "map": {
            "initialPosition": settings.GBIF_ALERT["MAIN_MAP_CONFIG"],
            "zoomLevelMinMaxQuery": settings.ZOOM_LEVEL_FOR_MIN_MAX_QUERY,
            "tileServerUrlTemplate": _build_mvt_url_template(
                "dashboard:internal-api:maps:mvt-tiles"
            ),
            "tileServerAggregatedUrlTemplate": _build_mvt_url_template(
                "dashboard:internal-api:maps:mvt-tiles-hexagon-grid-aggregated"
            ),
            "minMaxOccPerHexagonUrl": reverse(
                "dashboard:internal-api:maps:mvt-min-max-per-hexagon"
            ),
            "observationDetailsUrlTemplate": reverse(
                "dashboard:pages:observation-details",
                kwargs={"stable_id": "PLACEHOLDER"},
            ).replace("PLACEHOLDER", "{stable_id}"),
        },
        "speciesNameMode": species_name_mode,
        # Areas pre-selected in the home page's area filter. Public areas only:
        # Area.clean() enforces it, but clean() does not run on bulk updates or
        # loaddata, and a private geometry must never leak into every page.
        "defaultAreaIds": list(
            Area.objects.filter(
                is_default_home_filter=True, owner__isnull=True
            ).values_list("id", flat=True)
        ),
    }

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


EU_EMBLEM_STATIC_DIR = "eu-funding"
EU_EMBLEM_FALLBACK_LANGUAGE = "en"


@register.simple_tag
def eu_funding_emblem_path(negative: bool = False) -> str:
    """Static path of the official EU emblem matching the active language.

    The Commission ships one file per language, with the funding statement
    already typeset in it, so the file - not a translated caption next to a
    flag - is what carries the wording. We ship en/fr/nl (the languages this
    tool supports) and fall back to English when the active language has no
    asset, rather than showing nothing.

    `negative` selects the Commission's version for dark backgrounds (white
    lettering); the default is the positive/colour one.
    """
    suffix = "-negative" if negative else ""
    # `get_language()` can return a regional code ("en-us", the Django default
    # when nothing matched) while our assets are named by base language.
    language_code = (get_language() or EU_EMBLEM_FALLBACK_LANGUAGE).split("-")[0]

    candidate = f"{EU_EMBLEM_STATIC_DIR}/eu-funded-{language_code}{suffix}.png"
    if finders.find(candidate) is None:
        candidate = f"{EU_EMBLEM_STATIC_DIR}/eu-funded-{EU_EMBLEM_FALLBACK_LANGUAGE}{suffix}.png"
    return candidate
