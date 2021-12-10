import argparse
import tempfile
import datetime
from typing import Dict, Optional

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from dwca.read import DwCAReader  # type: ignore
from dwca.darwincore.utils import qualname as qn  # type: ignore
from dwca.rows import CoreRow  # type: ignore
from gbif_blocking_occurrences_download import download_occurrences as download_gbif_occurrences  # type: ignore
from maintenance_mode.core import set_maintenance_mode  # type: ignore

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
    taxon_key = int(
        get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/taxonKey")
    )
    try:
        return Species.objects.get(gbif_taxon_key=taxon_key)
    except Species.DoesNotExist:
        accepted_taxon_key = int(
            get_string_data(
                row, field_name="http://rs.gbif.org/terms/1.0/acceptedTaxonKey"
            )
        )
        return Species.objects.get(gbif_taxon_key=accepted_taxon_key)


def extract_gbif_download_id_from_dwca(dwca: DwCAReader) -> str:
    return dwca.metadata.find("dataset").find("alternateIdentifier").text


def get_string_data(row: CoreRow, field_name: str) -> str:
    """Extract string data from a row (with minor cleanup)"""
    return row.data[field_name].strip()


def get_float_data(row: CoreRow, field_name: str) -> float:
    """Extract float data from a row

    :raise ValueError if the value can't be converted
    """
    return float(get_string_data(row, field_name))


def get_int_data(row: CoreRow, field_name: str) -> int:
    """Extract int data from a row

    :raise ValueError if the value can't be converted
    """
    return int(get_string_data(row, field_name))


def import_single_occurrence(row: CoreRow, current_data_import: DataImport):
    # For-filtering data extraction
    year_str = get_string_data(row, field_name=qn("year"))

    try:
        point: Optional[Point] = Point(
            get_float_data(row, field_name=qn("decimalLongitude")),
            get_float_data(row, field_name=qn("decimalLatitude")),
            srid=4326,
        )
    except ValueError:
        point = None

    occurrence_id_str = get_string_data(row, field_name=qn("occurrenceID"))

    # Only import records with a year, coordinates and an occurrenceID
    if year_str != "" and point and occurrence_id_str != "":
        # Some dates are incomplete(year only)
        year = int(year_str)
        try:
            month = get_int_data(row, field_name=qn("month"))
            day = get_int_data(row, field_name=qn("day"))
        except ValueError:
            month = 1
            day = 1
        date = datetime.date(year, month, day)
        gbif_dataset_key = get_string_data(
            row, field_name="http://rs.gbif.org/terms/1.0/datasetKey"
        )
        dataset_name = get_string_data(row, field_name=qn("datasetName"))
        dataset, _ = Dataset.objects.get_or_create(
            gbif_dataset_key=gbif_dataset_key,
            defaults={"name": dataset_name},
        )
        new_occurrence = Occurrence.objects.create(
            gbif_id=int(
                get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/gbifID")
            ),
            occurrence_id=occurrence_id_str,
            species=species_for_row(row),
            location=point,
            date=date,
            data_import=current_data_import,
            source_dataset=dataset,
        )
        new_occurrence.migrate_linked_entities()


def send_successful_import_email():
    mail_admins(
        "Successful occurrence data import",
        "The daily occurrence data import has been successfully performed",
        fail_silently=True,
    )


def send_error_import_email():
    mail_admins(
        "ERROR during occurrence data import",
        "Please have a look at the application",
        fail_silently=True,
    )


class Command(BaseCommand):
    help = (
        "Import new occurrences and delete previous ones. "
        ""
        "By default, a new download is generated at GBIF. "
        "The --source-dwca option can be used to provide an existing local file instead."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_was_successful = False

    def _import_all_occurrences_from_dwca(
        self, dwca: DwCAReader, data_import: DataImport
    ):

        for core_row in dwca:
            import_single_occurrence(core_row, data_import)
            self.stdout.write(".", ending="")

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source-dwca",
            type=argparse.FileType("r"),
            help="Use an existing dwca file as source (otherwise a new GBIF download will be generated and downloaded)",
        )

    def flag_transaction_as_successful(self):
        self.transaction_was_successful = True

    def handle(self, *args, **options) -> None:
        self.stdout.write("(Re)importing all occurrences")

        # 1. Data preparation / download
        if options["source_dwca"]:
            self.stdout.write("Using a user-provided DWCA file")
            source_data_path = options["source_dwca"].name
        else:
            self.stdout.write(
                "No DWCA file provided, we'll generate and get a new GBIF download"
            )

            self.stdout.write(
                "Triggering a GBIF download and waiting for it - this can be long..."
            )
            tmp_file = tempfile.NamedTemporaryFile()
            source_data_path = tmp_file.name
            # This might takes several minutes...
            download_gbif_occurrences(
                build_gbif_predicate(
                    country_code=settings.RIPARIAS["TARGET_COUNTRY_CODE"],
                    species_list=Species.objects.all(),
                ),
                username=settings.RIPARIAS["GBIF_USERNAME"],
                password=settings.RIPARIAS["GBIF_PASSWORD"],
                output_path=source_data_path,
            )
            self.stdout.write("Occurrences downloaded")

        self.stdout.write(
            "We now have a (locally accessible) source dwca, real import is starting. We'll use a transaction and put "
            "the website in maintenance mode"
        )

        set_maintenance_mode(True)
        with transaction.atomic():
            transaction.on_commit(self.flag_transaction_as_successful)

            # 2. Create the DataImport object
            current_data_import = DataImport.objects.create(start=timezone.now())
            self.stdout.write(
                f"Created a new DataImport object: #{current_data_import.pk}"
            )

            # 3. Import data from DwCA (occurrences + GBIF download ID)
            with DwCAReader(source_data_path) as dwca:
                current_data_import.set_gbif_download_id(
                    extract_gbif_download_id_from_dwca(dwca)
                )
                self._import_all_occurrences_from_dwca(dwca, current_data_import)

            self.stdout.write(
                "All occurrences imported, now deleting occurrences linked to previous data imports..."
            )

            # 4. Remove previous occurrences
            Occurrence.objects.exclude(data_import=current_data_import).delete()

            # 4. Finalize the DataImport object
            self.stdout.write("Updating the DataImport object")
            current_data_import.complete()
            self.stdout.write("Done.")

        self.stdout.write("Leaving maintenance mode.")
        set_maintenance_mode(False)

        self.stdout.write("Sending email report")
        if self.transaction_was_successful:
            send_successful_import_email()
        else:
            send_error_import_email()
