import datetime
from typing import Annotated

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import HttpRequest
from ninja import NinjaAPI, Query
from ninja.errors import HttpError
from pydantic import Field

from dashboard.api_v2_schemas import (
    AreaOut,
    BasisOfRecordOut,
    CommentIn,
    CommentOut,
    DataImportOut,
    DatasetOut,
    FiltersQuery,
    HistogramEntryOut,
    ObservationDetailOut,
    ObservationsPageOut,
    SpeciesOut,
)
from dashboard.models import (
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
)
from markdownx.utils import markdownify  # type: ignore
from page_fragments.models import PageFragment

# Internal API v2 - powered by Django Ninja.
# This replaces the old internal-api/ endpoints incrementally (Phase 2+).
# The public api/ endpoints are left unchanged.
api_v2 = NinjaAPI(urls_namespace="api-v2")


@api_v2.get("/species/", response=list[SpeciesOut])
def species_list(request: HttpRequest):
    return [
        {
            "id": s.pk,
            "scientificName": s.name,
            "vernacularName": s.vernacular_name,
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


@api_v2.get("/basis-of-record/", response=list[BasisOfRecordOut])
def basis_of_record_list(request: HttpRequest):
    return [{"id": b.pk, "name": b.name} for b in BasisOfRecord.objects.all()]


@api_v2.get("/data-imports/", response=list[DataImportOut])
def data_imports_list(request: HttpRequest):
    return [
        {"id": di.pk, "name": f"Data import #{di.pk}", "startTimestamp": di.start}
        for di in DataImport.objects.order_by("-start")
    ]


_SORT_FIELD_MAP = {
    "date": "date",
    "scientificName": "species__name",
    "datasetName": "source_dataset__name",
    "municipality": "municipality",
    "verified": "verified",
}


@api_v2.get("/observations/", response=ObservationsPageOut, summary="List observations")
def observations_list(
    request: HttpRequest,
    filters: Query[FiltersQuery],
    page: int = 1,
    pageSize: int = 20,
    orderBy: Annotated[
        str,
        Field(description="Field to sort by. Accepted: date, scientificName, datasetName, municipality, verified. Unknown values fall back to date."),
    ] = "date",
    orderDir: Annotated[
        str,
        Field(description="Sort direction: asc or desc. Any value other than asc is treated as desc."),
    ] = "desc",
):
    """Return a paginated, filtered, and sorted page of observations.

    Pagination is controlled by `page` (1-based) and `pageSize` (capped at 100).
    Sorting is controlled by `orderBy` and `orderDir`. A secondary sort on `-pk`
    is always appended to guarantee stable pagination when the primary field has ties.
    """
    pageSize = min(max(pageSize, 1), 100)
    page = max(page, 1)

    user = request.user if request.user.is_authenticated else None

    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetsIds,
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

    total = qs.count()
    offset = (page - 1) * pageSize
    sort_field = _SORT_FIELD_MAP.get(orderBy, "date")
    sort_prefix = "" if orderDir == "asc" else "-"
    obs_page = list(qs.order_by(f"{sort_prefix}{sort_field}", "-pk")[offset : offset + pageSize])

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
            "vernacularName": obs.species.vernacular_name,
            "datasetName": obs.source_dataset.name,
            "date": obs.date,
            "municipality": obs.municipality,
            "verified": obs.verified,
            "identificationVerificationStatus": obs.identification_verification_status,
            "basisOfRecord": str(obs.basis_of_record),
            "seenByCurrentUser": (obs.pk not in unseen_ids) if user is not None else None,
        }
        for obs in obs_page
    ]

    return {"count": total, "items": items}


@api_v2.get("/observations/histogram/", response=list[HistogramEntryOut])
def observations_histogram(request: HttpRequest, filters: Query[FiltersQuery]):
    user = request.user if request.user.is_authenticated else None

    # Date filters are intentionally excluded: the histogram always shows the
    # full temporal distribution regardless of the user's date range selection.
    qs = Observation.objects.filtered_from_my_params(
        species_ids=filters.speciesIds,
        datasets_ids=filters.datasetsIds,
        basis_of_record_ids=filters.basisOfRecordIds,
        start_date=None,
        end_date=None,
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


@api_v2.get("/observations/{stable_id}/", response=ObservationDetailOut)
def observation_detail(request: HttpRequest, stable_id: str):
    try:
        obs = Observation.objects.select_related(
            "species", "source_dataset", "basis_of_record", "initial_data_import"
        ).get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    user = request.user if request.user.is_authenticated else None

    obs.mark_as_seen_by(request.user)

    seen_by_current_user: bool | None = None
    can_be_marked_unseen = False
    if user is not None:
        seen_by_current_user = obs.already_seen_by(user)
        if seen_by_current_user:
            can_be_marked_unseen = user.obs_match_alerts(obs)

    admin_url: str | None = None
    if request.user.is_authenticated and request.user.is_superuser:
        admin_url = obs.get_admin_url()

    lon, lat = obs.lonlat_4326_tuple

    comments = [
        {
            "id": c.pk,
            "authorUsername": c.author.username if c.author and not c.emptied_because_author_deleted_account else None,
            "createdAt": c.created_at,
            "text": c.text if not c.emptied_because_author_deleted_account else None,
            "deletedBecauseAuthorDeleted": c.emptied_because_author_deleted_account,
        }
        for c in obs.observationcomment_set.select_related("author").order_by("-created_at")
    ]

    return {
        "id": obs.pk,
        "stableId": obs.stable_id,
        "gbifId": obs.gbif_id,
        "lat": lat,
        "lon": lon,
        "scientificName": obs.species.name,
        "vernacularName": obs.species.vernacular_name,
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
        "basisOfRecord": str(obs.basis_of_record),
        "coordinateUncertaintyInMeters": obs.coordinate_uncertainty_in_meters,
        "initialDataImport": str(obs.initial_data_import),
        "seenByCurrentUser": seen_by_current_user,
        "canBeMarkedUnseen": can_be_marked_unseen,
        "adminUrl": admin_url,
        "comments": comments,
    }


@api_v2.post("/observations/{stable_id}/comments/", response=CommentOut)
def observation_add_comment(request: HttpRequest, stable_id: str, payload: CommentIn):
    if not request.user.is_authenticated:
        raise HttpError(403, "Authentication required")

    try:
        obs = Observation.objects.get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    text = payload.text.strip()
    if not text:
        raise HttpError(400, "Comment text cannot be empty")

    comment = ObservationComment.objects.create(
        observation=obs,
        author=request.user,
        text=text,
    )

    return {
        "id": comment.pk,
        "authorUsername": request.user.username,
        "createdAt": comment.created_at,
        "text": comment.text,
        "deletedBecauseAuthorDeleted": False,
    }


@api_v2.get("/page-fragments/{identifier}/", response=dict)
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


@api_v2.post("/observations/{stable_id}/mark-unseen/", response={200: dict, 403: dict})
def observation_mark_unseen(request: HttpRequest, stable_id: str):
    if not request.user.is_authenticated:
        raise HttpError(403, "Authentication required")

    try:
        obs = Observation.objects.get(stable_id=stable_id)
    except Observation.DoesNotExist:
        raise HttpError(404, "Observation not found")

    success = obs.mark_as_unseen_by(user=request.user)
    if not success:
        raise HttpError(403, "Cannot mark this observation as unseen")

    return 200, {"ok": True}
