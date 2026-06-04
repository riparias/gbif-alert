import datetime

from ninja import Schema
from pydantic import Field


class SpeciesOut(Schema):
    id: int
    scientificName: str
    vernacularNameEn: str
    vernacularNameNl: str
    vernacularNameFr: str
    gbifTaxonKey: int = Field(
        description=(
            "GBIF taxon key. Numeric in GBIF's data model, so returned as an "
            "integer. Distinct from `gbifId` (an occurrence identifier) which "
            "GBIF models as a string - the int/str split is intrinsic to GBIF, "
            "not an inconsistency in this API."
        )
    )
    tags: list[str]


class DatasetOut(Schema):
    id: int
    gbifKey: str
    name: str


class AreaOut(Schema):
    id: int
    name: str
    isUserSpecific: bool
    tags: list[str]


class BasisOfRecordOut(Schema):
    id: int
    name: str


class DataImportOut(Schema):
    id: int
    name: str
    startTimestamp: datetime.datetime
    endTimestamp: datetime.datetime | None
    importedCount: int
    newObservationsCount: int
    skippedCount: int
    gbifDownloadId: str


class FiltersQuery(Schema):
    speciesIds: list[int] = Field(default_factory=list)
    datasetIds: list[int] = Field(default_factory=list)
    basisOfRecordIds: list[int] = Field(default_factory=list)
    startDate: datetime.date | None = None
    endDate: datetime.date | None = None
    areaIds: list[int] = Field(default_factory=list)
    status: str | None = None
    initialDataImportIds: list[int] = Field(default_factory=list)
    verifiedFilter: str = "all"
    areaFilterMode: str = "inside"
    approachingDistanceKm: float | None = None


class ObservationOut(Schema):
    id: int
    stableId: str
    gbifId: str = Field(
        description=(
            "GBIF occurrence identifier. A string in GBIF's data model (unlike "
            "the numeric `gbifTaxonKey` on species), and returned as a string "
            "for fidelity to GBIF. The int/str split is intrinsic, not a bug."
        )
    )
    lat: float | None
    lon: float | None
    scientificName: str
    vernacularNameEn: str
    vernacularNameNl: str
    vernacularNameFr: str
    datasetName: str
    date: datetime.date
    municipality: str
    verified: bool
    identificationVerificationStatus: str  # empty string when not provided by GBIF
    basisOfRecordId: int
    seenByCurrentUser: bool | None = None


class ObservationsPageOut(Schema):
    count: int
    speciesCount: int
    datasetsCount: int
    items: list[ObservationOut]


class HistogramEntryOut(Schema):
    year: int
    month: int
    count: int


class CommentOut(Schema):
    id: int
    authorUsername: str | None
    createdAt: datetime.datetime
    text: str | None
    deletedBecauseAuthorDeleted: bool


class CommentIn(Schema):
    text: str


class ObservationDetailOut(Schema):
    id: int
    stableId: str
    gbifId: str = Field(
        description=(
            "GBIF occurrence identifier. A string in GBIF's data model (unlike "
            "the numeric `gbifTaxonKey` on species), and returned as a string "
            "for fidelity to GBIF. The int/str split is intrinsic, not a bug."
        )
    )
    lat: float | None
    lon: float | None
    scientificName: str
    vernacularNameEn: str
    vernacularNameNl: str
    vernacularNameFr: str
    datasetName: str
    datasetGbifKey: str
    date: datetime.date
    individualCount: int | None
    locality: str
    municipality: str
    recordedBy: str
    references: str
    identificationVerificationStatus: str  # empty string when not provided by GBIF
    verified: bool
    basisOfRecordId: int
    coordinateUncertaintyInMeters: float | None
    initialDataImport: str
    seenByCurrentUser: bool | None
    canBeMarkedUnseen: bool
    adminUrl: str | None
    comments: list[CommentOut]


class AlertNotificationFrequencyOut(Schema):
    id: str
    label: str


class AlertIn(Schema):
    name: str
    speciesIds: list[int]
    datasetIds: list[int] = Field(default_factory=list)
    basisOfRecordIds: list[int] = Field(default_factory=list)
    areaIds: list[int] = Field(default_factory=list)
    emailNotificationsFrequency: str = "W"
    verifiedFilter: str = "all"
    areaFilterMode: str = "inside"
    approachingDistanceKm: float | None = None


class AlertSpeciesOut(Schema):
    scientificName: str
    vernacularNameEn: str
    vernacularNameNl: str
    vernacularNameFr: str


class AlertOut(Schema):
    id: int
    name: str
    speciesIds: list[int]
    datasetIds: list[int]
    basisOfRecordIds: list[int]
    areaIds: list[int]
    emailNotificationsFrequency: str
    verifiedFilter: str
    areaFilterMode: str
    approachingDistanceKm: float | None
    unseenCount: int
    speciesDetails: list[AlertSpeciesOut]
    lastEmailSentAt: datetime.datetime | None


class AreaFromDrawingIn(Schema):
    name: str
    geojson: dict  # GeoJSON FeatureCollection, EPSG:4326


class AreaPatchIn(Schema):
    name: str | None = None
    geojson: dict | None = None  # None means "leave geometry unchanged"


class SignInIn(Schema):
    username: str
    password: str


class SignInOut(Schema):
    username: str


class SignUpIn(Schema):
    username: str
    firstName: str = ""
    lastName: str = ""
    email: str
    language: str
    password1: str
    password2: str


class PasswordChangeIn(Schema):
    oldPassword: str
    newPassword1: str
    newPassword2: str


class ProfileOut(Schema):
    username: str
    firstName: str
    lastName: str
    email: str
    language: str
    delayValue: int
    delayUnit: str


class ProfileIn(Schema):
    firstName: str
    lastName: str
    email: str
    language: str
    delayValue: int
    delayUnit: str


class DetailErrorOut(Schema):
    """Single-message error envelope.

    Used for all 4xx responses that do not carry per-field validation details.
    Equivalent in shape to django-ninja's default error body, made explicit so
    every endpoint declares it in its `response={...}` map and it appears in
    the OpenAPI schema.
    """

    detail: str


class ValidationErrorOut(Schema):
    """Field-validation error envelope.

    Used for 422 responses that carry per-field error messages. The top-level
    `detail` lets clients display a generic message when they don't iterate
    per-field; `errors` is a map of field name to a list of validation
    messages for that field.
    """

    detail: str
    errors: dict[str, list[str]]


class QueuedOut(Schema):
    """Acknowledgement that a bulk operation was queued for async processing.

    `count` is the number of rows the operation will affect (e.g. matching
    observations currently unseen by the user, for bulk mark-as-seen).
    """

    queued: bool
    count: int


class OkOut(Schema):
    """Simple boolean acknowledgement response."""

    ok: bool


class PageFragmentOut(Schema):
    """Rendered HTML for a page fragment (internal SPA helper endpoint)."""

    html: str


class AlertNameSuggestionOut(Schema):
    """A suggested, not-yet-used alert name (internal SPA helper endpoint)."""

    name: str


class GeoJSONFeatureOut(Schema):
    """A single GeoJSON Feature as produced by Django's geojson serializer.

    `geometry` and `properties` are passed through untyped - the schema
    documents the Feature envelope without constraining the geometry internals.
    """

    type: str
    id: int
    properties: dict
    geometry: dict | None


class GeoJSONFeatureCollectionOut(Schema):
    """A GeoJSON FeatureCollection (EPSG:4326) from Django's geojson serializer.

    Declares the exact members Django emits (`type`, `crs`, `features`) so that
    typing the response does not drop the `crs` member from the wire format.
    """

    type: str
    crs: dict
    features: list[GeoJSONFeatureOut]
