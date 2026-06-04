import datetime
import json
import tempfile
from typing import Annotated, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon as GEOSMultiPolygon
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers import serialize
from django.db.models import Count, F, Value
from django.db.models.functions import Coalesce, NullIf, TruncMonth
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language, gettext as _
from ninja import File, Form, NinjaAPI, Query
from ninja.files import UploadedFile
from ninja.errors import HttpError
from ninja.security import django_auth
from pydantic import Field

from dashboard.api_v2_schemas import (
    AlertIn,
    AlertNameSuggestionOut,
    AlertNotificationFrequencyOut,
    AlertOut,
    AreaFromDrawingIn,
    AreaOut,
    AreaPatchIn,
    BasisOfRecordOut,
    CommentIn,
    CommentOut,
    DataImportOut,
    DatasetOut,
    DetailErrorOut,
    FiltersQuery,
    GeoJSONFeatureCollectionOut,
    HistogramEntryOut,
    ObservationDetailOut,
    ObservationsPageOut,
    OkOut,
    PageFragmentOut,
    PasswordChangeIn,
    ProfileIn,
    ProfileOut,
    QueuedOut,
    SignInIn,
    SignInOut,
    SignUpIn,
    SpeciesOut,
    ValidationErrorOut,
)
from dashboard.forms import SignUpForm, _days_to_value_unit, _value_unit_to_days
from dashboard.geo_utils import file_to_wkt_multipolygon, geojson_to_multipolygon
from dashboard.utils import human_readable_git_version_number
from dashboard.views import jobs as background_jobs
from dashboard.models import (
    Alert,
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
    User,
)
from markdownx.utils import markdownify  # type: ignore
from page_fragments.models import PageFragment

# Internal API v2 - powered by Django Ninja.
# This replaces the old internal-api/ endpoints incrementally (Phase 2+).
# The public api/ endpoints are left unchanged.
api_v2 = NinjaAPI(
    urls_namespace="api-v2",
    title="GBIF Alert API",
    version=human_readable_git_version_number(),
    description=(
        "HTTP API powering the GBIF Alert single-page application. We are "
        "considering exposing this as a stable public API for external "
        "integrations; until that decision is made, endpoints, payloads, "
        "and error shapes may change between releases. For currently-stable "
        "external access, see the JSON endpoints under `/api/` and the OGC "
        "WFS service at `/api/wfs/observations/`.\n\n"
        "Source: https://github.com/riparias/gbif-alert"
    ),
    openapi_extra={
        "info": {
            "contact": {
                "name": "GBIF Alert maintainers",
                "url": "https://github.com/riparias/gbif-alert",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        }
    },
)

# Internal SPA helper API - a second Ninja instance mounted at /api/v2/spa/.
# These endpoints exist only to serve the single-page application; they are NOT
# part of the public API contract and may change or disappear between releases.
# Keeping them on a separate instance keeps the public /api/v2/ OpenAPI docs
# limited to endpoints we are willing to commit to.
api_v2_spa = NinjaAPI(
    urls_namespace="api-v2-spa",
    title="GBIF Alert SPA helper API",
    version=human_readable_git_version_number(),
    description=(
        "Internal helper endpoints for the GBIF Alert single-page application. "
        "These are not part of the public API contract and may change between "
        "releases. For the public API see `/api/v2/docs`.\n\n"
        "Source: https://github.com/riparias/gbif-alert"
    ),
    openapi_extra={
        "info": {
            "contact": {
                "name": "GBIF Alert maintainers",
                "url": "https://github.com/riparias/gbif-alert",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        }
    },
)


@api_v2.get("/species/", response=list[SpeciesOut])
def species_list(request: HttpRequest):
    return [
        {
            "id": s.pk,
            "scientificName": s.name,
            "vernacularNameEn": s.vernacular_name_en or "",
            "vernacularNameNl": s.vernacular_name_nl or "",
            "vernacularNameFr": s.vernacular_name_fr or "",
            "gbifTaxonKey": s.gbif_taxon_key,
            "tags": [t.name for t in s.tags.all()],
        }
        for s in Species.objects.prefetch_related("tags").all()
    ]


@api_v2.get("/datasets/", response=list[DatasetOut])
def datasets_list(request: HttpRequest):
    return [
        {"id": d.pk, "gbifKey": d.gbif_dataset_key, "name": d.name}
        for d in Dataset.objects.all()
    ]


@api_v2.get("/areas/", response=list[AreaOut])
def areas_list(request: HttpRequest):
    return [
        {
            "id": a.pk,
            "name": a.name,
            "isUserSpecific": a.is_user_specific,
            "tags": [t.name for t in a.tags.all()],
        }
        for a in Area.objects.available_to(request.user).prefetch_related("tags")
    ]


@api_v2.get("/areas/{area_id}/geojson/", response=GeoJSONFeatureCollectionOut)
def area_geojson(request: HttpRequest, area_id: int):
    """Return GeoJSON (FeatureCollection, EPSG:4326) for a single area.

    Available to any user who can access the area (public or owned).
    Returns 403 if the area exists but the user cannot access it.
    Returns 404 if the area does not exist.
    """
    area = get_object_or_404(Area, pk=area_id)
    if not area.is_available_to(request.user):
        raise HttpError(403, "Forbidden")
    return json.loads(serialize("geojson", [area], srid=4326))


@api_v2.post(
    "/areas/",
    response={201: AreaOut, 422: DetailErrorOut},
    auth=django_auth,
)
def area_create(
    request: HttpRequest,
    name: Form[str],
    data_file: File[UploadedFile],
):
    """Create a new user-specific area from an uploaded GeoPackage file.

    Returns 422 with a human-readable detail message if the file fails
    validation (wrong geometry type, multiple layers, missing SRS, etc.).
    """
    user = cast(User, request.user)
    with tempfile.NamedTemporaryFile(suffix=data_file.name) as tmp:
        tmp.write(data_file.read())
        tmp.flush()
        try:
            wkt = file_to_wkt_multipolygon(tmp.name)
        except ValueError as exc:
            return 422, {"detail": str(exc)}

    area = Area.objects.create(
        mpoly=cast(GEOSMultiPolygon, GEOSGeometry(wkt)), owner=user, name=name
    )
    return 201, {
        "id": area.pk,
        "name": area.name,
        "isUserSpecific": area.is_user_specific,
        "tags": [],
    }


@api_v2.post(
    "/areas/from-drawing/",
    response={201: AreaOut, 422: DetailErrorOut},
    auth=django_auth,
)
def area_create_from_drawing(request: HttpRequest, payload: AreaFromDrawingIn):
    """Create a new user-specific area from a GeoJSON FeatureCollection.

    Accepts a GeoJSON FeatureCollection (EPSG:4326) with Polygon or MultiPolygon
    features drawn by the user. All features are merged into a single MultiPolygon.

    Returns 422 with a detail message if the geometry is invalid.
    """
    user = cast(User, request.user)
    try:
        mpoly = geojson_to_multipolygon(payload.geojson)
    except ValueError as exc:
        return 422, {"detail": str(exc)}
    area = Area.objects.create(mpoly=mpoly, owner=user, name=payload.name)
    return 201, {
        "id": area.pk,
        "name": area.name,
        "isUserSpecific": area.is_user_specific,
        "tags": [],
    }


@api_v2.patch(
    "/areas/{area_id}/",
    response={200: AreaOut, 422: DetailErrorOut},
    auth=django_auth,
)
def area_patch(request: HttpRequest, area_id: int, payload: AreaPatchIn):
    """Update the name and/or geometry of a user-owned area.

    Both fields are optional. Passing geojson=None leaves the geometry unchanged.
    Returns 404 if the area does not exist or belongs to another user.
    """
    area = get_object_or_404(Area, pk=area_id, owner=request.user)
    if payload.name is not None:
        area.name = payload.name
    if payload.geojson is not None:
        try:
            area.mpoly = geojson_to_multipolygon(payload.geojson)
        except ValueError as exc:
            return 422, {"detail": str(exc)}
    area.save()
    return {
        "id": area.pk,
        "name": area.name,
        "isUserSpecific": area.is_user_specific,
        "tags": [t.name for t in area.tags.all()],
    }


@api_v2.delete(
    "/areas/{area_id}/",
    response={204: None, 409: DetailErrorOut},
    auth=django_auth,
)
def area_delete_endpoint(request: HttpRequest, area_id: int):
    """Delete a user-owned area.

    Returns 404 if the area does not exist or belongs to another user.
    Returns 409 with a detail message if any alerts reference this area.
    """
    area = get_object_or_404(Area, pk=area_id, owner=request.user)
    try:
        area.delete()
    except Area.HasAlerts:
        return 409, {
            "detail": str(
                _(
                    "The area cannot be deleted because it has alerts associated with it."
                )
            )
        }
    return 204, None


@api_v2.get("/basis-of-record/", response=list[BasisOfRecordOut])
def basis_of_record_list(request: HttpRequest):
    return [{"id": b.pk, "name": b.name} for b in BasisOfRecord.objects.all()]


@api_v2.get("/data-imports/", response=list[DataImportOut])
def data_imports_list(request: HttpRequest):
    qs = DataImport.objects.order_by("-start").annotate(
        new_observations_count=Count("occurrences_initially_imported")
    )
    return [
        {
            "id": di.pk,
            "name": f"Data import #{di.pk}",
            "startTimestamp": di.start,
            "endTimestamp": di.end,
            "importedCount": di.imported_observations_counter,
            "newObservationsCount": di.new_observations_count,
            "skippedCount": di.skipped_observations_counter,
            "gbifDownloadId": di.gbif_download_id,
        }
        for di in qs
    ]


_SIMPLE_SORT_FIELD_MAP = {
    "date": "date",
    "scientificName": "species__name",
    "datasetName": "source_dataset__name",
    "municipality": "municipality",
    "verified": "verified",
}

# Set of orderBy values that need locale-aware annotation rather than a
# direct column reference. Kept separate so the simple map stays minimal.
_LOCALISED_SORT_FIELDS = {"vernacularName"}

# Active language codes recognised when picking the vernacular_name_<lang>
# column. Mirrors the pattern in dashboard/views/maps.py.
_VERNACULAR_LANG_CODES = {code[:2] for code, _name in settings.LANGUAGES}

# Every orderBy value the list endpoint accepts. Unknown values are rejected
# with 400 rather than silently coerced to date (audit M8).
_ACCEPTED_ORDER_BY = set(_SIMPLE_SORT_FIELD_MAP) | _LOCALISED_SORT_FIELDS


@api_v2.get(
    "/observations/",
    response={200: ObservationsPageOut, 400: DetailErrorOut},
    summary="List observations",
)
def observations_list(
    request: HttpRequest,
    filters: Query[FiltersQuery],
    page: int = 1,
    pageSize: int = 20,
    orderBy: Annotated[
        str,
        Field(
            description="Field to sort by. Accepted: date, scientificName, vernacularName, datasetName, municipality, verified. An unknown value returns 400."
        ),
    ] = "date",
    orderDir: Annotated[
        str,
        Field(
            description="Sort direction: asc or desc. Any other value returns 400."
        ),
    ] = "desc",
):
    """Return a paginated, filtered, and sorted page of observations.

    Pagination is controlled by `page` (1-based) and `pageSize` (must be 1-100).
    Sorting is controlled by `orderBy` and `orderDir`. A secondary sort on `-pk`
    is always appended to guarantee stable pagination when the primary field has ties.
    Invalid `orderBy`, `orderDir`, `page`, or `pageSize` values return 400.
    """
    if orderBy not in _ACCEPTED_ORDER_BY:
        accepted = ", ".join(sorted(_ACCEPTED_ORDER_BY))
        return 400, {
            "detail": f"Invalid orderBy '{orderBy}'. Accepted values: {accepted}."
        }
    if orderDir not in ("asc", "desc"):
        return 400, {"detail": "Invalid orderDir. Accepted values: asc, desc."}
    if not 1 <= pageSize <= 100:
        return 400, {"detail": "Invalid pageSize. Must be between 1 and 100."}
    if page < 1:
        return 400, {"detail": "Invalid page. Must be 1 or greater."}

    user = request.user if request.user.is_authenticated else None

    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetIds,
        basis_of_record_ids=filters.basisOfRecordIds,
        start_date=filters.startDate,
        end_date=filters.endDate,
        areas_ids=filters.areaIds,
        status_for_user=filters.status,
        initial_data_import_ids=filters.initialDataImportIds,
        user=user,
        verified_filter=filters.verifiedFilter,
        area_filter_mode=filters.areaFilterMode,
        approaching_distance_km=filters.approachingDistanceKm,
    )

    aggregates = qs.aggregate(
        total=Count("pk"),
        species_count=Count("species_id", distinct=True),
        datasets_count=Count("source_dataset_id", distinct=True),
    )
    total: int = aggregates["total"]
    offset = (page - 1) * pageSize
    sort_prefix = "" if orderDir == "asc" else "-"

    if orderBy in _LOCALISED_SORT_FIELDS:
        # Build a sort key that falls back to the scientific name when the
        # vernacular column is empty for the active locale. django-modeltranslation
        # uses one column per language: vernacular_name_en, vernacular_name_fr,
        # vernacular_name_nl. Normalise the active locale to a known two-letter
        # code to avoid building a field name that doesn't exist (e.g. "fr-be").
        lang = get_language() or "en"
        lang_code = lang[:2] if lang[:2] in _VERNACULAR_LANG_CODES else "en"
        field = f"species__vernacular_name_{lang_code}"
        annotated_qs = qs.annotate(
            vernacular_sort_key=Coalesce(
                NullIf(F(field), Value("")),
                F("species__name"),
            )
        )
        ordered = annotated_qs.order_by(f"{sort_prefix}vernacular_sort_key", "-pk")
    else:
        sort_field = _SIMPLE_SORT_FIELD_MAP.get(orderBy, "date")
        ordered = qs.order_by(f"{sort_prefix}{sort_field}", "-pk")  # type: ignore[assignment]

    obs_page = list(ordered[offset : offset + pageSize])

    # Fetch unseen status for the current page in one extra query
    if user is not None and obs_page:
        unseen_ids: set[int] = set(
            ObservationUnseen.objects.filter(
                observation_id__in=[obs.pk for obs in obs_page], user=user
            ).values_list("observation_id", flat=True)
        )
    else:
        unseen_ids = set()

    items = [
        {
            "id": obs.pk,
            "stableId": obs.stable_id,
            "gbifId": obs.gbif_id,
            "lat": obs.lat,
            "lon": obs.lon,
            "scientificName": obs.species.name,
            "vernacularNameEn": obs.species.vernacular_name_en or "",
            "vernacularNameNl": obs.species.vernacular_name_nl or "",
            "vernacularNameFr": obs.species.vernacular_name_fr or "",
            "datasetName": obs.source_dataset.name,
            "date": obs.date,
            "municipality": obs.municipality,
            "verified": obs.verified,
            "identificationVerificationStatus": obs.identification_verification_status,
            "basisOfRecordId": obs.basis_of_record_id,
            "seenByCurrentUser": (obs.pk not in unseen_ids)
            if user is not None
            else None,
        }
        for obs in obs_page
    ]

    return 200, {
        "count": total,
        "speciesCount": aggregates["species_count"],
        "datasetsCount": aggregates["datasets_count"],
        "items": items,
    }


@api_v2.get("/observations/histogram/", response=list[HistogramEntryOut])
def observations_histogram(request: HttpRequest, filters: Query[FiltersQuery]):
    user = request.user if request.user.is_authenticated else None

    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetIds,
        basis_of_record_ids=filters.basisOfRecordIds,
        start_date=filters.startDate,
        end_date=filters.endDate,
        areas_ids=filters.areaIds,
        status_for_user=filters.status,
        initial_data_import_ids=filters.initialDataImportIds,
        user=user,
        verified_filter=filters.verifiedFilter,
        area_filter_mode=filters.areaFilterMode,
        approaching_distance_km=filters.approachingDistanceKm,
    )

    rows = (
        qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    return [
        {"year": row["month"].year, "month": row["month"].month, "count": row["total"]}
        for row in rows
    ]


@api_v2.post(
    "/observations/mark-as-seen/",
    response={200: QueuedOut},
    auth=django_auth,
)
def observations_mark_all_as_seen(request: HttpRequest, filters: Query[FiltersQuery]):
    """Bulk-mark all observations matching the current filters as seen by
    the requesting user. Runs asynchronously via django-rq."""
    user = cast(User, request.user)
    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetIds,
        basis_of_record_ids=filters.basisOfRecordIds,
        start_date=filters.startDate,
        end_date=filters.endDate,
        areas_ids=filters.areaIds,
        status_for_user=filters.status,
        initial_data_import_ids=filters.initialDataImportIds,
        user=user,
        verified_filter=filters.verifiedFilter,
        area_filter_mode=filters.areaFilterMode,
        approaching_distance_km=filters.approachingDistanceKm,
    )
    background_jobs.mark_many_observations_as_seen.delay(qs, user)
    return 200, {"queued": True}


@api_v2.get("/observations/{stable_id}/", response=ObservationDetailOut)
def observation_detail(request: HttpRequest, stable_id: str):
    try:
        obs = Observation.objects.select_related(
            "species", "source_dataset", "basis_of_record", "initial_data_import"
        ).get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    user = request.user if request.user.is_authenticated else None

    seen_by_current_user: bool | None = None
    can_be_marked_unseen = False
    if user is not None:
        seen_by_current_user = obs.already_seen_by(user)
        # canBeMarkedUnseen is a capability flag: the drawer marks the obs seen
        # on open, so it no longer depends on the obs already being seen at GET
        # time (audit M11). GET itself no longer mutates seen state.
        can_be_marked_unseen = user.obs_match_alerts(obs)

    admin_url: str | None = None
    if request.user.is_authenticated and request.user.is_superuser:
        admin_url = obs.get_admin_url()

    lon, lat = obs.lonlat_4326_tuple

    comments = [
        {
            "id": c.pk,
            "authorUsername": c.author.username
            if c.author and not c.emptied_because_author_deleted_account
            else None,
            "createdAt": c.created_at,
            "text": c.text if not c.emptied_because_author_deleted_account else None,
            "deletedBecauseAuthorDeleted": c.emptied_because_author_deleted_account,
        }
        for c in obs.observationcomment_set.select_related("author").order_by(
            "-created_at"
        )
    ]

    return {
        "id": obs.pk,
        "stableId": obs.stable_id,
        "gbifId": obs.gbif_id,
        "lat": lat,
        "lon": lon,
        "scientificName": obs.species.name,
        "vernacularNameEn": obs.species.vernacular_name_en or "",
        "vernacularNameNl": obs.species.vernacular_name_nl or "",
        "vernacularNameFr": obs.species.vernacular_name_fr or "",
        "datasetName": obs.source_dataset.name,
        "datasetGbifKey": obs.source_dataset.gbif_dataset_key,
        "date": obs.date,
        "individualCount": obs.individual_count,
        "locality": obs.locality,
        "municipality": obs.municipality,
        "recordedBy": obs.recorded_by,
        "references": obs.references,
        "identificationVerificationStatus": obs.identification_verification_status,
        "verified": obs.verified,
        "basisOfRecordId": obs.basis_of_record_id,
        "coordinateUncertaintyInMeters": obs.coordinate_uncertainty_in_meters,
        "initialDataImport": str(obs.initial_data_import),
        "seenByCurrentUser": seen_by_current_user,
        "canBeMarkedUnseen": can_be_marked_unseen,
        "adminUrl": admin_url,
        "comments": comments,
    }


@api_v2.post(
    "/observations/{stable_id}/comments/",
    response={200: CommentOut, 422: DetailErrorOut},
    auth=django_auth,
)
def observation_add_comment(request: HttpRequest, stable_id: str, payload: CommentIn):
    user = cast(User, request.user)
    try:
        obs = Observation.objects.get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    text = payload.text.strip()
    if not text:
        # Well-formed body but semantically invalid -> 422 (audit N3).
        return 422, {"detail": "Comment text cannot be empty"}

    comment = ObservationComment.objects.create(
        observation=obs,
        author=user,
        text=text,
    )

    return 200, {
        "id": comment.pk,
        "authorUsername": user.username,
        "createdAt": comment.created_at,
        "text": comment.text,
        "deletedBecauseAuthorDeleted": False,
    }


@api_v2_spa.get("/page-fragments/{identifier}/", response=PageFragmentOut)
def page_fragment(request: HttpRequest, identifier: str):
    """Return the rendered HTML for a page fragment in the current request language.

    Returns {"html": ""} if the fragment does not exist, so callers never need
    to handle 404 - a missing fragment simply shows nothing.
    """
    try:
        fragment = PageFragment.objects.get(identifier=identifier)
        html = markdownify(fragment.get_content_in(request.LANGUAGE_CODE))
    except PageFragment.DoesNotExist:
        html = ""
    return {"html": html}


@api_v2.post(
    "/observations/{stable_id}/mark-as-seen/",
    response={200: OkOut},
    auth=django_auth,
)
def observation_mark_as_seen(request: HttpRequest, stable_id: str):
    """Mark a single observation as seen by the requesting user.

    Replaces the implicit side effect that the detail GET used to perform, so
    that GET stays safe/idempotent (audit M11).
    """
    try:
        obs = Observation.objects.get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    obs.mark_as_seen_by(cast(User, request.user))
    return 200, {"ok": True}


@api_v2.post(
    "/observations/{stable_id}/mark-unseen/",
    response={200: OkOut, 403: DetailErrorOut},
    auth=django_auth,
)
def observation_mark_unseen(request: HttpRequest, stable_id: str):
    try:
        obs = Observation.objects.get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    success = obs.mark_as_unseen_by(user=request.user)
    if not success:
        raise HttpError(403, "Cannot mark this observation as unseen")

    return 200, {"ok": True}


# --- Alert helpers ---


def _alert_to_out(alert: Alert) -> dict:
    return {
        "id": alert.pk,
        "name": alert.name,
        "speciesIds": [s.pk for s in alert.species.all()],
        "datasetIds": [d.pk for d in alert.datasets.all()],
        "basisOfRecordIds": [b.pk for b in alert.basis_of_record_filters.all()],
        "areaIds": [a.pk for a in alert.areas.all()],
        "emailNotificationsFrequency": alert.email_notifications_frequency,
        "verifiedFilter": alert.verified_filter,
        "areaFilterMode": alert.area_filter_mode,
        "approachingDistanceKm": alert.approaching_distance_km,
        "unseenCount": alert.unseen_observations().count(),
        "speciesDetails": [
            {"scientificName": s.name, "vernacularName": s.vernacular_name}
            for s in alert.species.all()
        ],
        "speciesList": alert.species_list,
        "areaDescription": alert.area_description,
        "areaNames": list(alert.areas.order_by("name").values_list("name", flat=True)),
        "datasetNames": list(
            alert.datasets.order_by("name").values_list("name", flat=True)
        ),
        "datasetsList": alert.datasets_list,
        "basisOfRecordList": alert.basis_of_record_list,
        "verifiedFilterDisplay": alert.verified_filter_display,
        "emailNotificationsFrequencyDisplay": alert.get_email_notifications_frequency_display(),
        "lastEmailSentAt": alert.last_email_sent_on,
    }


def _save_alert(alert: Alert, payload: AlertIn) -> dict[str, list[str]]:
    """Apply payload to alert instance, validate, save if valid.

    Returns an errors dict - empty means success.
    Does NOT save if there are errors.
    """
    alert.name = payload.name
    alert.email_notifications_frequency = payload.emailNotificationsFrequency
    alert.verified_filter = payload.verifiedFilter
    alert.area_filter_mode = payload.areaFilterMode
    alert.approaching_distance_km = payload.approachingDistanceKm

    errors: dict[str, list[str]] = {}

    if not payload.speciesIds:
        errors["species"] = [str(_("At least one species must be selected"))]

    if payload.areaFilterMode != Alert.AREA_FILTER_INSIDE and not payload.areaIds:
        errors["area_filter_mode"] = [
            str(
                _("At least one area must be selected for the chosen area filter mode.")
            )
        ]

    try:
        alert.full_clean()
    except DjangoValidationError as e:
        for field, msgs in e.message_dict.items():
            errors[field] = [str(m) for m in msgs]

    if not errors:
        alert.save()
        alert.species.set(payload.speciesIds)
        alert.areas.set(payload.areaIds)
        alert.datasets.set(payload.datasetIds)
        alert.basis_of_record_filters.set(payload.basisOfRecordIds)

    return errors


# --- Alert endpoints ---
# NOTE: suggest-name and notification-frequencies are listed BEFORE {alert_id}
# routes so they are not captured as alert IDs.


@api_v2_spa.get(
    "/alerts/suggest-name/", response=AlertNameSuggestionOut, auth=django_auth
)
def alert_suggest_name(request: HttpRequest):
    """Suggest the next available 'My alert #N' name for the current user."""
    user = cast(User, request.user)
    existing = set(Alert.objects.filter(user=user).values_list("name", flat=True))
    n = 1
    while f"My alert #{n}" in existing:
        n += 1
    return {"name": f"My alert #{n}"}


# No auth required - frequency choices are not user-specific.
@api_v2.get(
    "/alerts/notification-frequencies/",
    response=list[AlertNotificationFrequencyOut],
)
def alert_notification_frequencies(request: HttpRequest):
    """List available email notification frequency choices."""
    return [{"id": k, "label": str(v)} for k, v in Alert.EMAIL_NOTIFICATION_CHOICES]


@api_v2.get("/alerts/", response=list[AlertOut], auth=django_auth)
def alerts_list(request: HttpRequest):
    """Return all alerts belonging to the authenticated user."""
    user = cast(User, request.user)
    alerts = (
        Alert.objects.filter(user=user)
        .prefetch_related("species", "datasets", "areas", "basis_of_record_filters")
        .order_by("id")
    )
    return [_alert_to_out(a) for a in alerts]


@api_v2.post(
    "/alerts/", response={201: AlertOut, 422: ValidationErrorOut}, auth=django_auth
)
def alert_create(request: HttpRequest, payload: AlertIn):
    """Create a new alert for the authenticated user."""
    alert = Alert(user=cast(User, request.user))
    errors = _save_alert(alert, payload)
    if errors:
        return 422, {"detail": "Validation failed", "errors": errors}
    return 201, _alert_to_out(alert)


@api_v2.get("/alerts/{alert_id}/", response=AlertOut, auth=django_auth)
def alert_detail(request: HttpRequest, alert_id: int):
    """Return one alert. 404 if it does not belong to the current user."""
    alert = get_object_or_404(
        Alert.objects.prefetch_related(
            "species", "datasets", "areas", "basis_of_record_filters"
        ),
        id=alert_id,
        user=request.user,
    )
    return _alert_to_out(alert)


@api_v2.put(
    "/alerts/{alert_id}/",
    response={200: AlertOut, 422: ValidationErrorOut},
    auth=django_auth,
)
def alert_update(request: HttpRequest, alert_id: int, payload: AlertIn):
    """Update an existing alert. 404 if it does not belong to the current user."""
    alert = get_object_or_404(
        Alert.objects.prefetch_related(
            "species", "datasets", "areas", "basis_of_record_filters"
        ),
        id=alert_id,
        user=request.user,
    )
    errors = _save_alert(alert, payload)
    if errors:
        return 422, {"detail": "Validation failed", "errors": errors}
    return 200, _alert_to_out(alert)


@api_v2.delete("/alerts/{alert_id}/", response={204: None}, auth=django_auth)
def alert_delete(request: HttpRequest, alert_id: int):
    """Delete an alert. 404 if it does not belong to the current user."""
    alert = get_object_or_404(Alert, id=alert_id, user=request.user)
    alert.delete()
    return 204, None


# ---- Auth endpoints ----


@api_v2.post(
    "/auth/signin/",
    response={200: SignInOut, 401: DetailErrorOut},
    auth=None,
)
def auth_signin(request: HttpRequest, payload: SignInIn):
    """Authenticate and create a session. Returns 401 on bad credentials."""
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        return 401, {"detail": str(_("Invalid username or password."))}
    login(request, user)
    return 200, {"username": user.get_username()}


@api_v2.post(
    "/auth/signup/",
    response={201: SignInOut, 422: ValidationErrorOut},
    auth=None,
)
def auth_signup(request: HttpRequest, payload: SignUpIn):
    """Create an account and log in. Returns 422 with field errors on failure."""
    form = SignUpForm(
        data={
            "username": payload.username,
            "first_name": payload.firstName,
            "last_name": payload.lastName,
            "email": payload.email,
            "language": payload.language,
            "password1": payload.password1,
            "password2": payload.password2,
        }
    )
    if not form.is_valid():
        # Django form field names are snake_case; remap the two renamed fields
        # back to the API's camelCase names so the request and error shapes agree.
        key_map = {"first_name": "firstName", "last_name": "lastName"}
        errors: dict[str, list[str]] = {
            key_map.get(field, field): [str(msg) for msg in msgs]
            for field, msgs in form.errors.items()
        }
        return 422, {"detail": "Validation failed", "errors": errors}
    user = form.save()
    login(request, user)
    return 201, {"username": user.get_username()}


@api_v2.post(
    "/auth/password-change/",
    response={204: None, 422: ValidationErrorOut},
    auth=django_auth,
)
def auth_password_change(request: HttpRequest, payload: PasswordChangeIn):
    """Change password. Returns 204 on success, 422 with field errors on failure."""
    user = cast(User, request.user)
    if not user.check_password(payload.oldPassword):
        return 422, {
            "detail": "Validation failed",
            "errors": {"oldPassword": [str(_("The old password is incorrect."))]},
        }
    if payload.newPassword1 != payload.newPassword2:
        return 422, {
            "detail": "Validation failed",
            "errors": {"newPassword2": [str(_("The two passwords do not match."))]},
        }
    user.set_password(payload.newPassword1)
    user.save()
    update_session_auth_hash(request, user)
    return 204, None


@api_v2_spa.post(
    "/news/mark-visited/",
    response={204: None},
    auth=None,
)
def news_mark_visited(request: HttpRequest):
    """Mark news as visited for the current user. No-op for anonymous users."""
    if request.user.is_authenticated:
        request.user.mark_news_as_visited_now()
    return 204, None


@api_v2.get(
    "/profile/",
    response=ProfileOut,
    auth=django_auth,
)
def profile_get(request: HttpRequest):
    """Return the current user's editable profile fields."""
    user = cast(User, request.user)
    value, unit = _days_to_value_unit(user.notification_delay_days)
    return {
        "username": user.get_username(),
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email,
        "language": user.language,
        "delayValue": value,
        "delayUnit": unit,
    }


@api_v2.put(
    "/profile/",
    response={200: ProfileOut, 422: ValidationErrorOut},
    auth=django_auth,
)
def profile_put(request: HttpRequest, payload: ProfileIn):
    """Save profile changes. Returns 422 with field errors on duplicate email."""
    user = cast(User, request.user)
    # Validate unique email (excluding self)
    if User.objects.filter(email=payload.email).exclude(pk=user.pk).exists():
        return 422, {
            "detail": "Validation failed",
            "errors": {"email": [str(_("This email address is already in use."))]},
        }
    valid_units = ("days", "weeks", "months", "years")
    if payload.delayUnit not in valid_units:
        return 422, {
            "detail": "Validation failed",
            "errors": {"delayUnit": ["Invalid unit."]},
        }
    user.first_name = payload.firstName
    user.last_name = payload.lastName
    user.email = payload.email
    user.language = payload.language
    user.notification_delay_days = _value_unit_to_days(
        payload.delayValue, payload.delayUnit
    )
    user.save()
    value, unit = _days_to_value_unit(user.notification_delay_days)
    return 200, {
        "username": user.get_username(),
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email,
        "language": user.language,
        "delayValue": value,
        "delayUnit": unit,
    }


@api_v2.delete(
    "/account/",
    response={204: None},
    auth=django_auth,
)
def account_delete(request: HttpRequest):
    """Delete the current user account and log out."""
    user = request.user
    user.delete()
    logout(request)
    return 204, None
