from datetime import datetime

from ninja import Schema


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
    startTimestamp: datetime
