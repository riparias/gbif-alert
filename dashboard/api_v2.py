import datetime
import json
import tempfile
from typing import Annotated, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.gis.geos import (
    GEOSException,
    GEOSGeometry,
    MultiPolygon as GEOSMultiPolygon,
)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers import serialize
from django.db.models import Count, F, Value
from django.db.models.functions import Coalesce, NullIf, TruncMonth
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language, gettext as _
from ninja import File, Form, NinjaAPI, Query
from ninja.files import UploadedFile
from ninja.errors import HttpError
from ninja.security import django_auth
from ninja.throttling import AnonRateThrottle, AuthRateThrottle
from pydantic import Field

from dashboard.api_v2_schemas import (
    AlertIn,
    AlertNameSuggestionOut,
    AlertFromTemplateIn,
    AlertNotificationFrequencyOut,
    AlertOut,
    AlertTemplateOut,
    AlertTemplatePublishedOut,
    ApiTokenCreateIn,
    ApiTokenCreatedOut,
    ApiTokenOut,
    AreaFilterMode,
    AreaIn,
    AreaOut,
    AreaPatchIn,
    BasisOfRecordOut,
    CommentIn,
    CommentOut,
    CountOut,
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
    SpeciesIn,
    SpeciesOut,
    SpeciesPerPolygonIn,
    SpeciesPerPolygonOut,
    UserStatusOut,
    ValidationErrorOut,
    VerifiedFilter,
)
from dashboard.api_v2_auth import ApiTokenAuth
from dashboard.forms import SignUpForm, _days_to_value_unit, _value_unit_to_days
from dashboard.geo_utils import file_to_wkt_multipolygon, geojson_to_multipolygon
from dashboard.utils import human_readable_git_version_number
from dashboard.views import jobs as background_jobs
from dashboard.views.helpers import api_status_to_internal
from dashboard.models import (
    Alert,
    AlertTemplate,
    ApiToken,
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

# Rate limits for the public API: anonymous per IP, authenticated (session or
# token) per user. Module-level so tests can adjust them. Rates come from
# settings (env-overridable). api_v2_spa is internal and stays unthrottled.
api_v2_anon_throttle = AnonRateThrottle(settings.API_V2_THROTTLE_ANON)
api_v2_auth_throttle = AuthRateThrottle(settings.API_V2_THROTTLE_AUTH)

# Public API v2 - powered by Django Ninja. The supported HTTP API for
# programmatic access; it also powers the web app. (The /api/v2/spa/ instance
# defined below is internal-only and not part of the public contract.)
api_v2 = NinjaAPI(
    urls_namespace="api-v2",
    title="GBIF Alert API",
    throttle=[api_v2_anon_throttle, api_v2_auth_throttle],
    version=human_readable_git_version_number(),
    description=(
        "GBIF Alert's stable, supported public HTTP API for programmatic access "
        "to its data. It also powers the GBIF Alert web app. An OGC WFS service "
        "is available at `/api/wfs/observations/`.\n\n"
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

# Implicit error responses that django-ninja produces without us returning them
# explicitly. They all share the DetailErrorOut shape ({"detail": "..."}), the
# same body ninja renders for auth failures, CSRF failures and not-found errors.
# We merge these into the relevant `response=` maps (via `**ERR_401` etc.) so
# they appear in the public OpenAPI schema. This is purely declarative: ninja
# renders exception-driven responses through its own handlers, so adding these
# keys does not change runtime behaviour.
ERR_401 = {401: DetailErrorOut}  # missing or invalid credentials
ERR_403 = {403: DetailErrorOut}  # session write without a valid CSRF token
ERR_404 = {404: DetailErrorOut}  # object not found, or not owned by the user


def _vernacular_names(species: Species) -> dict[str, str]:
    """The species' vernacular name in all three languages, as flat fields (N6).

    django-modeltranslation creates the per-language columns at runtime, so they
    are invisible to the static type checker - hence the localized ignores here,
    kept in one place rather than scattered across every builder.
    """
    return {
        "vernacularNameEn": species.vernacular_name_en or "",  # type: ignore[attr-defined]
        "vernacularNameNl": species.vernacular_name_nl or "",  # type: ignore[attr-defined]
        "vernacularNameFr": species.vernacular_name_fr or "",  # type: ignore[attr-defined]
    }


def _species_to_out(species: Species) -> dict:
    """Build the SpeciesOut payload for a single species.

    Shared by the list, per-polygon, and create endpoints so the field mapping
    lives in one place. Callers that add extra keys (per-polygon adds an
    observation count) spread this result and add their own.
    """
    return {
        "id": species.pk,
        "scientificName": species.name,
        **_vernacular_names(species),
        "gbifTaxonKey": species.gbif_taxon_key,
        "gbifColTaxonKey": species.gbif_col_taxon_key,
        "tags": [t.name for t in species.tags.all()],
        "imageUrl": species.image_url,
        "imageSourceUrl": species.image_source_url,
        "imageAttribution": species.image_attribution,
        "imageLicense": species.image_license,
        "imageSourceType": species.image_source_type,
    }


@api_v2.get("/species/", response=list[SpeciesOut])
def species_list(request: HttpRequest):
    return [
        _species_to_out(s)
        for s in Species.objects.prefetch_related("tags")  # type: ignore[misc]  # taggit manager not resolvable by django-stubs.all()
    ]


@api_v2.post(
    "/species/",
    response={201: SpeciesOut, 422: ValidationErrorOut, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
)
def species_create(request: HttpRequest, payload: SpeciesIn):
    """Create a species. Superusers (operators) only.

    Species must exist before observations can be imported for them (the import
    command keys on gbif_col_taxon_key), so operators need a way to add them;
    this is the programmatic equivalent of the admin's Species form.

    Returns 403 for authenticated non-superusers, and 422 (with per-field
    errors) for a duplicate gbifTaxonKey, a blank scientificName, or a species
    with neither taxon key.
    """
    user = cast(User, request.user)
    if not user.is_superuser:
        raise HttpError(403, "Only operators can create species.")

    species = Species(
        name=payload.scientificName,
        gbif_taxon_key=payload.gbifTaxonKey,
        gbif_col_taxon_key=payload.gbifColTaxonKey,
        vernacular_name_en=payload.vernacularNameEn,  # type: ignore[misc]  # modeltranslation column
        vernacular_name_fr=payload.vernacularNameFr,  # type: ignore[misc]  # modeltranslation column
        vernacular_name_nl=payload.vernacularNameNl,  # type: ignore[misc]  # modeltranslation column
        image_url=payload.imageUrl,
        image_source_url=payload.imageSourceUrl,
        image_attribution=payload.imageAttribution,
        image_license=payload.imageLicense,
        # Derived, never client-set - mirrors SpeciesAdmin.save_model.
        image_source_type=(Species.ImageSourceType.MANUAL if payload.imageUrl else ""),
    )

    try:
        species.full_clean()
    except DjangoValidationError as exc:
        # Remap snake_case model fields to the API's camelCase field names so the
        # error keys match the request shape (same approach as auth_signup).
        key_map = {
            "name": "scientificName",
            "gbif_taxon_key": "gbifTaxonKey",
            "gbif_col_taxon_key": "gbifColTaxonKey",
            "vernacular_name_en": "vernacularNameEn",
            "vernacular_name_fr": "vernacularNameFr",
            "vernacular_name_nl": "vernacularNameNl",
            "image_url": "imageUrl",
            "image_source_url": "imageSourceUrl",
        }
        errors = {
            key_map.get(field, field): [str(m) for m in msgs]
            for field, msgs in exc.message_dict.items()
        }
        return 422, {"detail": "Validation failed", "errors": errors}

    species.save()
    species.tags.set(payload.tags)
    return 201, _species_to_out(species)


@api_v2.post(
    "/species/per-polygon/",
    response={200: list[SpeciesPerPolygonOut], 422: DetailErrorOut},
)
def species_per_polygon(request: HttpRequest, payload: SpeciesPerPolygonIn):
    """Species occurring within the given polygon, each with its observation count.

    The polygon is a GeoJSON FeatureCollection in EPSG:4326, sent in the request
    body. (The legacy endpoint took WKT in the query string - audit N1.)
    """
    try:
        # Returns a geometry already projected to DATA_SRID (matches location).
        mpoly = geojson_to_multipolygon(payload.geojson)
    except (ValueError, KeyError, TypeError, GEOSException) as exc:
        return 422, {"detail": f"Invalid GeoJSON: {exc}"}

    qs = (
        Species.objects.filter(observation__location__within=mpoly)
        .annotate(num_observations=Count("observation"))
        .prefetch_related("tags")  # type: ignore[misc]  # taggit manager not resolvable by django-stubs
    )
    return 200, [
        {
            **_species_to_out(s),
            "observationCountInPolygon": s.num_observations,
        }
        for s in qs
    ]


@api_v2.get("/datasets/", response=list[DatasetOut])
def datasets_list(request: HttpRequest):
    return [
        {"id": d.pk, "gbifDatasetKey": d.gbif_dataset_key, "name": d.name}
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
        for a in Area.objects.available_to(request.user).prefetch_related("tags")  # type: ignore[misc]  # taggit manager not resolvable by django-stubs
    ]


@api_v2.get(
    "/areas/{area_id}/geojson/",
    response={200: GeoJSONFeatureCollectionOut, **ERR_403, **ERR_404},
)
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


def _area_to_out(area: Area) -> dict:
    """Build the AreaOut payload for a single area."""
    return {
        "id": area.pk,
        "name": area.name,
        "isUserSpecific": area.is_user_specific,
        "tags": [t.name for t in area.tags.all()],
    }


def _area_name_taken(
    name: str, owner: User | None, exclude_pk: int | None = None
) -> bool:
    """Whether an area of that name already exists in the same scope.

    Scope is the owner: a public area and a user's own area may share a name,
    but two public areas - or two areas of the same user - may not.

    Parameters
    ----------
    name : str
        Candidate area name.
    owner : User or None
        None for the public scope, the owning user otherwise.
    exclude_pk : int or None
        Primary key to ignore, so an area does not collide with itself on
        rename.

    Returns
    -------
    bool
    """
    qs = Area.objects.filter(name=name, owner=owner)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _resolve_area_owner(user: User, shared: bool) -> User | None:
    """Owner for a new area: None (public) when an operator asks for a shared one.

    Parameters
    ----------
    user : User
        The authenticated caller.
    shared : bool
        Whether the caller asked for an area visible to everyone.

    Returns
    -------
    User or None
        None for a shared area, the caller otherwise.

    Raises
    ------
    HttpError
        403 if a non-superuser asks for a shared area.
    """
    if not shared:
        return user
    if not user.is_superuser:
        raise HttpError(403, "Only operators can create shared areas.")
    return None


def _get_editable_area(user: User, area_id: int) -> Area:
    """Fetch an area the user is allowed to modify.

    A user may modify their own areas; an operator (superuser) may also modify
    public ones, since those are site content. Another user's private area is
    off-limits to everyone, operators included.

    Parameters
    ----------
    user : User
        The authenticated caller.
    area_id : int
        Primary key of the area.

    Returns
    -------
    Area

    Raises
    ------
    Http404
        If the area does not exist, or the user may not modify it. Not-found
        and not-allowed are deliberately indistinguishable, as before.
    """
    area = get_object_or_404(Area, pk=area_id)
    if area.is_owned_by(user) or (area.is_public and user.is_superuser):
        return area
    raise Http404


@api_v2.post(
    "/areas/",
    response={
        201: AreaOut,
        409: DetailErrorOut,
        422: DetailErrorOut,
        **ERR_401,
        **ERR_403,
    },
    auth=[ApiTokenAuth(), django_auth],
)
def area_create(request: HttpRequest, payload: AreaIn):
    """Create an area from GeoJSON.

    Accepts a FeatureCollection, a single Feature, or a bare Polygon /
    MultiPolygon geometry, in EPSG:4326. All polygons are merged into a single
    MultiPolygon - one call creates exactly one area.

    Operators can pass `shared` to create an area visible to every user;
    anyone else doing so is refused with 403.

    Returns 422 with a detail message if the geometry is unusable.
    Returns 409 if an area of that name already exists in the same scope
    (the caller's areas, or the public ones).
    """
    user = cast(User, request.user)
    owner = _resolve_area_owner(user, payload.shared)
    try:
        mpoly = geojson_to_multipolygon(payload.geojson)
    except ValueError as exc:
        return 422, {"detail": str(exc)}
    if _area_name_taken(payload.name, owner):
        return 409, {"detail": str(_("An area with this name already exists."))}
    area = Area.objects.create(mpoly=mpoly, owner=owner, name=payload.name)
    area.tags.set(payload.tags)
    return 201, _area_to_out(area)


@api_v2.post(
    "/areas/from-file/",
    response={
        201: AreaOut,
        409: DetailErrorOut,
        422: DetailErrorOut,
        **ERR_401,
        **ERR_403,
    },
    auth=[ApiTokenAuth(), django_auth],
)
def area_create_from_file(
    request: HttpRequest,
    name: Form[str],
    data_file: File[UploadedFile],
    shared: Form[bool] = False,
    tags: Form[list[str]] = [],
):
    """Create a new user-specific area from an uploaded GeoPackage file.

    Operators can pass `shared` to create an area visible to every user;
    anyone else doing so is refused with 403.

    Returns 422 with a human-readable detail message if the file fails
    validation (wrong geometry type, multiple layers, missing SRS, etc.).
    Returns 409 if an area of that name already exists in the same scope
    (the caller's areas, or the public ones).
    """
    user = cast(User, request.user)
    owner = _resolve_area_owner(user, shared)
    with tempfile.NamedTemporaryFile(suffix=data_file.name) as tmp:
        tmp.write(data_file.read())
        tmp.flush()
        try:
            wkt = file_to_wkt_multipolygon(tmp.name)
        except ValueError as exc:
            return 422, {"detail": str(exc)}

    if _area_name_taken(name, owner):
        return 409, {"detail": str(_("An area with this name already exists."))}

    area = Area.objects.create(
        mpoly=cast(GEOSMultiPolygon, GEOSGeometry(wkt)), owner=owner, name=name
    )
    area.tags.set(tags)
    return 201, _area_to_out(area)


@api_v2.patch(
    "/areas/{area_id}/",
    response={
        200: AreaOut,
        409: DetailErrorOut,
        422: DetailErrorOut,
        **ERR_401,
        **ERR_403,
        **ERR_404,
    },
    auth=[ApiTokenAuth(), django_auth],
)
def area_patch(request: HttpRequest, area_id: int, payload: AreaPatchIn):
    """Update the name and/or geometry of an area the caller may modify.

    Both fields are optional. Passing geojson=None leaves the geometry unchanged.
    Returns 404 if the area does not exist, or the caller may not modify it
    (their own areas, plus the public ones for operators).
    Returns 409 if an area of that name already exists in the same scope
    (the caller's areas, or the public ones).
    """
    area = _get_editable_area(cast(User, request.user), area_id)
    if payload.name is not None and payload.name != area.name:
        if _area_name_taken(payload.name, area.owner, exclude_pk=area.pk):
            return 409, {"detail": str(_("An area with this name already exists."))}
        area.name = payload.name
    if payload.geojson is not None:
        try:
            area.mpoly = geojson_to_multipolygon(payload.geojson)
        except ValueError as exc:
            return 422, {"detail": str(exc)}
    if payload.tags is not None:
        area.tags.set(payload.tags)
    area.save()
    return _area_to_out(area)


@api_v2.delete(
    "/areas/{area_id}/",
    response={204: None, 409: DetailErrorOut, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
)
def area_delete(request: HttpRequest, area_id: int):
    """Delete an area the caller may modify.

    Returns 404 if the area does not exist, or the caller may not modify it
    (their own areas, plus the public ones for operators).
    Returns 409 with a detail message if any alerts reference this area.
    """
    area = _get_editable_area(cast(User, request.user), area_id)
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
            "startedAt": di.start,
            "endedAt": di.end,
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
        Field(description="Sort direction: asc or desc. Any other value returns 400."),
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
        status_for_user=api_status_to_internal(filters.status),
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
            **_vernacular_names(obs.species),
            "datasetName": obs.source_dataset.name,
            "date": obs.date,
            "municipality": obs.municipality,
            "verified": obs.verified,
            "identificationVerificationStatus": obs.identification_verification_status,
            "basisOfRecordId": obs.basis_of_record_id,
            "basisOfRecordName": obs.basis_of_record.name,
            "viewedByCurrentUser": (obs.pk not in unseen_ids)
            if user is not None
            else None,
        }
        for obs in obs_page
    ]

    total_pages = (total + pageSize - 1) // pageSize  # 0 when there are no results
    return 200, {
        "count": total,
        "speciesCount": aggregates["species_count"],
        "datasetsCount": aggregates["datasets_count"],
        "page": page,
        "pageSize": pageSize,
        "totalPages": total_pages,
        "hasNextPage": page < total_pages,
        "hasPreviousPage": page > 1,
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
        status_for_user=api_status_to_internal(filters.status),
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


@api_v2.get("/observations/counter/", response=CountOut)
def observations_counter(request: HttpRequest, filters: Query[FiltersQuery]):
    """Return only the count of observations matching the filters - a lightweight
    alternative to the full list when the consumer just needs the number.

    Defined before observation_detail so the literal `/observations/counter/`
    path is matched ahead of `/observations/{stable_id}/`.
    """
    user = request.user if request.user.is_authenticated else None
    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetIds,
        basis_of_record_ids=filters.basisOfRecordIds,
        start_date=filters.startDate,
        end_date=filters.endDate,
        areas_ids=filters.areaIds,
        status_for_user=api_status_to_internal(filters.status),
        initial_data_import_ids=filters.initialDataImportIds,
        user=user,
        verified_filter=filters.verifiedFilter,
        area_filter_mode=filters.areaFilterMode,
        approaching_distance_km=filters.approachingDistanceKm,
    )
    return {"count": qs.count()}


@api_v2.post(
    "/observations/mark-as-viewed/",
    response={200: QueuedOut, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
)
def observations_mark_all_as_seen(request: HttpRequest, filters: FiltersQuery):
    """Bulk-mark all observations matching the given filters as seen by the
    requesting user. Runs asynchronously via django-rq.

    Filters are read from the JSON request body (a mutating POST carries its
    payload in the body, not the query string - audit N4).
    """
    user = cast(User, request.user)
    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetIds,
        basis_of_record_ids=filters.basisOfRecordIds,
        start_date=filters.startDate,
        end_date=filters.endDate,
        areas_ids=filters.areaIds,
        status_for_user=api_status_to_internal(filters.status),
        initial_data_import_ids=filters.initialDataImportIds,
        user=user,
        verified_filter=filters.verifiedFilter,
        area_filter_mode=filters.areaFilterMode,
        approaching_distance_km=filters.approachingDistanceKm,
    )
    # N2: report how many matching observations are currently unseen by the user
    # (the rows the job will actually flip), so the consumer knows what happened.
    count = qs.filter(observationunseen__user=user).distinct().count()
    background_jobs.mark_many_observations_as_seen.delay(qs, user)
    return 200, {"queued": True, "count": count}


@api_v2.get(
    "/observations/{stable_id}/",
    response={200: ObservationDetailOut, **ERR_404},
)
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
        # canBeMarkedNotViewed is a capability flag: the drawer marks the obs seen
        # on open, so it no longer depends on the obs already being seen at GET
        # time (audit M11). GET itself no longer mutates seen state.
        can_be_marked_unseen = user.obs_match_alerts(obs)

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
        **_vernacular_names(obs.species),
        "datasetName": obs.source_dataset.name,
        "gbifDatasetKey": obs.source_dataset.gbif_dataset_key,
        "date": obs.date,
        "individualCount": obs.individual_count,
        "locality": obs.locality,
        "municipality": obs.municipality,
        "recordedBy": obs.recorded_by,
        "references": obs.references,
        "identificationVerificationStatus": obs.identification_verification_status,
        "verified": obs.verified,
        "basisOfRecordId": obs.basis_of_record_id,
        "basisOfRecordName": obs.basis_of_record.name,
        "coordinateUncertaintyInMeters": obs.coordinate_uncertainty_in_meters,
        "initialDataImport": obs.initial_data_import.as_dict,
        "viewedByCurrentUser": seen_by_current_user,
        "canBeMarkedNotViewed": can_be_marked_unseen,
        "comments": comments,
    }


@api_v2.post(
    "/observations/{stable_id}/comments/",
    response={200: CommentOut, 422: DetailErrorOut, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
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
    "/observations/{stable_id}/mark-as-viewed/",
    response={200: OkOut, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
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
    "/observations/{stable_id}/mark-as-not-viewed/",
    response={200: OkOut, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
)
def observation_mark_as_unseen(request: HttpRequest, stable_id: str):
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
        "notViewedCount": alert.unseen_observations().count(),
        "speciesDetails": [
            {"scientificName": s.name, **_vernacular_names(s)}
            for s in alert.species.all()
        ],
        "lastEmailSentAt": alert.last_email_sent_on,
    }


def _alert_template_to_out(template: "AlertTemplate") -> dict:
    return {
        "id": template.pk,
        "nameEn": template.name_en or "",  # type: ignore[attr-defined]
        "nameFr": template.name_fr or "",  # type: ignore[attr-defined]
        "nameNl": template.name_nl or "",  # type: ignore[attr-defined]
        "descriptionEn": template.description_en or "",  # type: ignore[attr-defined]
        "descriptionFr": template.description_fr or "",  # type: ignore[attr-defined]
        "descriptionNl": template.description_nl or "",  # type: ignore[attr-defined]
        "speciesIds": [s.pk for s in template.species.all()],
        "datasetIds": [d.pk for d in template.datasets.all()],
        "basisOfRecordIds": [b.pk for b in template.basis_of_record_filters.all()],
        "areaIds": [a.pk for a in template.areas.all()],
        "verifiedFilter": template.verified_filter,
        "areaFilterMode": template.area_filter_mode,
        "approachingDistanceKm": template.approaching_distance_km,
        "speciesDetails": [
            {"scientificName": s.name, **_vernacular_names(s)}
            for s in template.species.all()
        ],
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


@api_v2.get(
    "/alerts/",
    response={200: list[AlertOut], **ERR_401},
    auth=[ApiTokenAuth(), django_auth],
)
def alerts_list(request: HttpRequest):
    """Return all alerts belonging to the authenticated user."""
    user = cast(User, request.user)
    alerts = (
        Alert.objects.filter(user=user)
        .prefetch_related("species", "datasets", "areas", "basis_of_record_filters")
        .order_by("id")
    )
    return [_alert_to_out(a) for a in alerts]


@api_v2.get(
    "/alert-templates/",
    response={200: list[AlertTemplateOut], **ERR_401},
    auth=[ApiTokenAuth(), django_auth],
)
def alert_templates_list(request: HttpRequest):
    """Return all published alert templates, operator-ordered."""
    templates = AlertTemplate.objects.prefetch_related(
        "species", "datasets", "areas", "basis_of_record_filters"
    ).all()  # Meta.ordering applies (display_order, name)
    return [_alert_template_to_out(t) for t in templates]


@api_v2.post(
    "/alerts/",
    response={201: AlertOut, 422: ValidationErrorOut, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
)
def alert_create(request: HttpRequest, payload: AlertIn):
    """Create a new alert for the authenticated user."""
    alert = Alert(user=cast(User, request.user))
    errors = _save_alert(alert, payload)
    if errors:
        return 422, {"detail": "Validation failed", "errors": errors}
    return 201, _alert_to_out(alert)


@api_v2.post(
    "/alerts/from-template/",
    response={201: AlertOut, 422: ValidationErrorOut, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
)
def alert_create_from_template(request: HttpRequest, payload: AlertFromTemplateIn):
    """Create a new alert for the current user by copying a template's filters."""
    template: AlertTemplate = get_object_or_404(
        AlertTemplate.objects.prefetch_related(
            "species", "datasets", "areas", "basis_of_record_filters"
        ),
        id=payload.templateId,
    )
    alert = Alert(user=cast(User, request.user), created_from_template=template)
    alert_in = AlertIn(
        name=payload.name,
        speciesIds=[s.pk for s in template.species.all()],
        datasetIds=[d.pk for d in template.datasets.all()],
        basisOfRecordIds=[b.pk for b in template.basis_of_record_filters.all()],
        areaIds=[a.pk for a in template.areas.all()],
        emailNotificationsFrequency=payload.emailNotificationsFrequency,
        verifiedFilter=cast(VerifiedFilter, template.verified_filter),
        areaFilterMode=cast(AreaFilterMode, template.area_filter_mode),
        approachingDistanceKm=template.approaching_distance_km,
    )
    errors = _save_alert(alert, alert_in)
    if errors:
        return 422, {"detail": "Validation failed", "errors": errors}
    return 201, _alert_to_out(alert)


@api_v2.get(
    "/alerts/{alert_id}/",
    response={200: AlertOut, **ERR_401, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
)
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
    response={200: AlertOut, 422: ValidationErrorOut, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
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


@api_v2.delete(
    "/alerts/{alert_id}/",
    response={204: None, **ERR_401, **ERR_403, **ERR_404},
    auth=[ApiTokenAuth(), django_auth],
)
def alert_delete(request: HttpRequest, alert_id: int):
    """Delete an alert. 404 if it does not belong to the current user."""
    alert = get_object_or_404(Alert, id=alert_id, user=request.user)
    alert.delete()
    return 204, None


@api_v2_spa.post(
    "/alerts/{alert_id}/publish-as-template/",
    response={201: AlertTemplatePublishedOut, **ERR_401, **ERR_403, **ERR_404},
    auth=django_auth,
)
def alert_publish_as_template(request: HttpRequest, alert_id: int):
    """Promote an existing alert to a live template. Operators (superusers) only."""
    user = cast(User, request.user)
    if not user.is_superuser:
        raise HttpError(403, "Only operators can publish templates.")
    alert = get_object_or_404(
        Alert.objects.prefetch_related(
            "species", "datasets", "areas", "basis_of_record_filters"
        ),
        id=alert_id,
    )
    template = AlertTemplate.create_from_alert(alert, created_by=user)
    return 201, {"id": template.pk}


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
    "/auth/signout/",
    response={204: None, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
)
def auth_signout(request: HttpRequest):
    """End the current session. Returns 204."""
    logout(request)
    return 204, None


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
    response={204: None, 422: ValidationErrorOut, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
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


@api_v2_spa.get(
    "/user-status/",
    response=UserStatusOut,
    auth=None,
)
def user_status(request: HttpRequest):
    """Return the current values of the navbar notification dots.

    Anonymous users get False for both flags (they see no dots).
    """
    user = request.user
    if not user.is_authenticated:
        return {"hasUnseenNews": False, "hasAlertsWithUnseenObservations": False}
    return {
        "hasUnseenNews": user.has_unseen_news,
        "hasAlertsWithUnseenObservations": user.has_alerts_with_unseen_observations,
    }


@api_v2.get(
    "/profile/",
    response={200: ProfileOut, **ERR_401},
    auth=[ApiTokenAuth(), django_auth],
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
    response={200: ProfileOut, 422: ValidationErrorOut, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
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
    response={204: None, **ERR_401, **ERR_403},
    auth=[ApiTokenAuth(), django_auth],
)
def account_delete(request: HttpRequest):
    """Delete the current user account and log out."""
    user = request.user
    user.delete()
    logout(request)
    return 204, None


# --- API tokens (personal access tokens) ---
# Managed from the logged-in SPA, so these are session-only (you cannot mint or
# revoke tokens using a token).


def _api_token_to_out(token: ApiToken) -> dict:
    return {
        "id": token.pk,
        "name": token.name,
        "prefix": token.prefix,
        "createdAt": token.created_at,
        "lastUsedAt": token.last_used_at,
    }


@api_v2.get(
    "/api-tokens/",
    response={200: list[ApiTokenOut], **ERR_401},
    auth=django_auth,
)
def api_tokens_list(request: HttpRequest):
    """List the current user's API tokens (never the secret value)."""
    user = cast(User, request.user)
    return [_api_token_to_out(t) for t in user.api_tokens.all()]


@api_v2.post(
    "/api-tokens/",
    response={201: ApiTokenCreatedOut, 422: DetailErrorOut, **ERR_401, **ERR_403},
    auth=django_auth,
)
def api_token_create(request: HttpRequest, payload: ApiTokenCreateIn):
    """Create a token and return its raw value once (never retrievable again)."""
    user = cast(User, request.user)
    name = payload.name.strip()
    if not name:
        return 422, {"detail": "A token name is required."}
    token, raw = ApiToken.create_for(user, name=name)
    return 201, {**_api_token_to_out(token), "token": raw}


@api_v2.delete(
    "/api-tokens/{token_id}/",
    response={204: None, **ERR_401, **ERR_403, **ERR_404},
    auth=django_auth,
)
def api_token_delete(request: HttpRequest, token_id: int):
    """Revoke one of the current user's tokens."""
    user = cast(User, request.user)
    deleted, _ = ApiToken.objects.filter(pk=token_id, user=user).delete()
    if not deleted:
        raise HttpError(404, "Token not found")
    return 204, None
