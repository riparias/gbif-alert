from django.http import HttpRequest
from ninja import NinjaAPI

from dashboard.api_v2_schemas import (
    AreaOut,
    BasisOfRecordOut,
    DataImportOut,
    DatasetOut,
    SpeciesOut,
)
from dashboard.models import Area, BasisOfRecord, DataImport, Dataset, Species

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
