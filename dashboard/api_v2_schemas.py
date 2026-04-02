import datetime

from ninja import Schema
from pydantic import Field


class SpeciesOut(Schema):
    id: int
    scientificName: str
    vernacularName: str
    gbifTaxonKey: int
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


class FiltersQuery(Schema):
    speciesIds: list[int] = Field(default_factory=list)
    datasetsIds: list[int] = Field(default_factory=list)
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
    gbifId: str
    lat: float | None
    lon: float | None
    scientificName: str
    vernacularName: str
    datasetName: str
    date: datetime.date
    municipality: str
    verified: bool
    identificationVerificationStatus: str  # empty string when not provided by GBIF
    basisOfRecord: str
    seenByCurrentUser: bool | None = None


class ObservationsPageOut(Schema):
    count: int
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
    gbifId: str
    lat: float | None
    lon: float | None
    scientificName: str
    vernacularName: str
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
    basisOfRecord: str
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
    vernacularName: str


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
    speciesList: str
    areaDescription: str
    areaNames: list[str]
    datasetNames: list[str]
    datasetsList: str
    basisOfRecordList: str
    verifiedFilterDisplay: str
    emailNotificationsFrequencyDisplay: str
    lastEmailSentOn: datetime.datetime | None


class AlertValidationErrorOut(Schema):
    errors: dict[str, list[str]]
