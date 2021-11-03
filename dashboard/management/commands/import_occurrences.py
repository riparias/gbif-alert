import tempfile
import datetime
from pathlib import Path
from typing import Dict, Optional

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from django.utils import timezone
from dwca.read import DwCAReader  # type: ignore
from dwca.darwincore.utils import qualname as qn  # type: ignore
from dwca.rows import CoreRow  # type: ignore
from gbif_blocking_occurrences_download import download_occurrences  # type: ignore

from dashboard.models import Species, Occurrence, DataImport, Dataset


def build_gbif_predicate(country_code: str, species_list: QuerySet[Species]) -> Dict:
    """Build a GBIF predicate (for occurrence download) targeting a specific country and a list of species"""
    return {
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "COUNTRY", "value": country_code},
                {
                    "type": "in",
                    "key": "TAXON_KEY",
                    "values": [f"{s.gbif_taxon_key}" for s in species_list],
                },
            ],
        }
    }


def species_for_row(row: CoreRow) -> Species:
    """Based first on taxonKey, with fallback to acceptedTaxonKey"""
    taxon_key = int(row.data["http://rs.gbif.org/terms/1.0/taxonKey"])
    try:
        return Species.objects.get(gbif_taxon_key=taxon_key)
    except Species.DoesNotExist:
        accepted_taxon_key = int(
            row.data["http://rs.gbif.org/terms/1.0/acceptedTaxonKey"]
        )
        return Species.objects.get(gbif_taxon_key=accepted_taxon_key)


def extract_gbif_download_id_from_dwca(dwca: DwCAReader) -> str:
    return dwca.metadata.find("dataset").find("alternateIdentifier").text


def import_single_occurrence(row: CoreRow, current_data_import: DataImport):
    # For-filtering data extraction
    year_str = row.data[qn("year")]

    try:
        point: Optional[Point] = Point(
            float(row.data[qn("decimalLongitude")]),
            float(row.data[qn("decimalLatitude")]),
            srid=4326,
        )
    except ValueError:
        point = None

    if year_str != "" and point:  # Only process records with a year and coordinates
        # Some dates are incomplete(year only)
        year = int(year_str)
        try:
            month = int(row.data[qn("month")])
            day = int(row.data[qn("day")])
        except ValueError:
            month = 1
            day = 1
        date = datetime.date(year, month, day)
        gbif_dataset_key = row.data["http://rs.gbif.org/terms/1.0/datasetKey"]
        dataset_name = row.data[qn("datasetName")]
        dataset, _ = Dataset.objects.get_or_create(
            gbif_id=gbif_dataset_key,
            defaults={"name": dataset_name},
        )
        Occurrence.objects.create(
            gbif_id=int(row.data["http://rs.gbif.org/terms/1.0/gbifID"]),
            species=species_for_row(row),
            location=point,
            date=date,
            data_import=current_data_import,
            source_dataset=dataset,
        )


class Command(BaseCommand):
    help = "Download and refresh all occurrence data from GBIF"

    def handle(self, *args, **options) -> None:
        self.stdout.write("(Re)importing all occurrences from GBIF")
        predicate = build_gbif_predicate(
            country_code=settings.RIPARIAS["TARGET_COUNTRY_CODE"],
            species_list=Species.objects.all(),
        )

        with tempfile.TemporaryDirectory() as dirname:
            self.stdout.write(
                "Triggering a GBIF download and waiting for it - this can be long..."
            )

            current_data_import = DataImport.objects.create(start=timezone.now())
            self.stdout.write(f"Current data import: #{current_data_import.pk}")

            download_dest = Path(dirname, "download.zip")
            # This might takes several minutes...
            download_occurrences(
                predicate,
                username=settings.RIPARIAS["GBIF_USERNAME"],
                password=settings.RIPARIAS["GBIF_PASSWORD"],
                output_path=download_dest,
            )

            self.stdout.write("Occurrences downloaded")

            self.stdout.write("Importing freshly downloaded occurrences")
            with DwCAReader(download_dest) as dwca:
                current_data_import.gbif_download_id = (
                    extract_gbif_download_id_from_dwca(dwca)
                )
                current_data_import.save()

                for core_row in dwca:
                    import_single_occurrence(core_row, current_data_import)
                    self.stdout.write(".", ending="")

                self.stdout.write(
                    "All occurrences imported, now deleting occurrences linked to previous data imports..."
                )
                Occurrence.objects.exclude(data_import=current_data_import).delete()

                self.stdout.write("Updating the DataImport object")
                current_data_import.end = timezone.now()
                current_data_import.completed = True
                current_data_import.imported_occurrences_counter = (
                    Occurrence.objects.filter(data_import=current_data_import).count()
                )
                current_data_import.save()

        self.stdout.write("Done.")
