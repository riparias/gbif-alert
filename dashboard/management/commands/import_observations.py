import argparse
import datetime
import tempfile
from functools import cache
from typing import Literal

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.db import transaction
from django.utils import timezone
from dwca.darwincore.utils import qualname as qn  # type: ignore
from dwca.read import DwCAReader  # type: ignore
from dwca.rows import CoreRow  # type: ignore
from gbif_blocking_occurrences_download import download_occurrences as download_gbif_occurrences  # type: ignore
from maintenance_mode.core import set_maintenance_mode  # type: ignore

from dashboard.management.commands.helpers import get_dataset_name_from_gbif_api
from dashboard.models import Species, Observation, DataImport, Dataset


def species_for_row(row: CoreRow, hash_species) -> Species:
    """Based first on taxonKey, with fallback to acceptedTaxonKey then speciesKey

    Returns None if the corresponding species cannot be found
    """
    taxon_key = int(
        get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/taxonKey")
    )

    accepted_taxon_key = int(
        get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/acceptedTaxonKey")
    )

    species_key = int(
        get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/speciesKey")
    )

    try:
        return hash_species[taxon_key]
    except KeyError:
        try:
            return hash_species[accepted_taxon_key]
        except KeyError:
            return hash_species[species_key]


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


def build_single_observation(
    row: CoreRow,
    current_data_import: DataImport,
    hash_datasets: dict[str, Dataset],
    hash_species: dict[str, Species],
) -> Observation | Literal[False]:
    """Import a single observation into the database

    :raise: Species.DoesNotExist if the species referenced in the row cannot be found in the database

    :return True if successful, False if observation was skipped (=unusable OR is an absence)
    """
    # For-filtering data extraction
    year_str = get_string_data(row, field_name=qn("year"))

    try:
        point: Point | None = Point(
            get_float_data(row, field_name=qn("decimalLongitude")),
            get_float_data(row, field_name=qn("decimalLatitude")),
            srid=4326,
        )
    except ValueError:
        point = None

    occurrence_id_str = get_string_data(row, field_name=qn("occurrenceID"))
    occurrence_status_str = get_string_data(row, field_name=qn("occurrenceStatus"))

    # Only import records with a year, coordinates, an occurrenceID which represent "presence" data
    if (
        year_str != ""
        and point
        and occurrence_id_str != ""
        and occurrence_status_str == "PRESENT"
    ):
        # Some dates are incomplete, we're good as long as we have a year
        year = int(year_str)
        try:
            month = get_int_data(row, field_name=qn("month"))
        except ValueError:
            month = 1

        try:
            day = get_int_data(row, field_name=qn("day"))
        except ValueError:
            day = 1

        date = datetime.date(year, month, day)
        gbif_dataset_key = get_string_data(
            row, field_name="http://rs.gbif.org/terms/1.0/datasetKey"
        )

        try:
            individual_count: int | None = get_int_data(
                row, field_name=qn("individualCount")
            )
        except ValueError:
            individual_count = None

        try:
            coordinates_uncertainty: float | None = get_float_data(
                row, field_name=qn("coordinateUncertaintyInMeters")
            )
        except ValueError:
            coordinates_uncertainty = None

        new_observation = Observation(
            gbif_id=int(
                get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/gbifID")
            ),
            occurrence_id=occurrence_id_str,
            species=species_for_row(row, hash_species),
            location=point,
            date=date,
            data_import=current_data_import,
            source_dataset=hash_datasets[gbif_dataset_key],
            individual_count=individual_count,
            locality=get_string_data(row, field_name=qn("locality")),
            municipality=get_string_data(row, field_name=qn("municipality")),
            basis_of_record=get_string_data(row, field_name=qn("basisOfRecord")),
            recorded_by=get_string_data(row, field_name=qn("recordedBy")),
            coordinate_uncertainty_in_meters=coordinates_uncertainty,
            references=get_string_data(row, field_name=qn("references")),
        )
        new_observation.set_or_migrate_initial_data_import(
            current_data_import=current_data_import
        )
        return new_observation

    return False  # Observation was skipped


def send_successful_import_email():
    mail_admins(
        "Successful observations data import",
        "The daily observation data import has been successfully performed",
        fail_silently=True,
    )


def send_error_import_email():
    mail_admins(
        "ERROR during observation data import",
        "Please have a look at the application",
        fail_silently=True,
    )


class Command(BaseCommand):
    help = (
        "Import new observations and delete previous ones. "
        ""
        "By default, a new download is generated at GBIF. "
        "The --source-dwca option can be used to provide an existing local file instead."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_was_successful = False

    def _import_all_observations_from_dwca(
        self,
        dwca: DwCAReader,
        data_import: DataImport,
        hash_table_datasets: dict,
        hash_table_species: dict,
    ) -> int:
        """:return the number of skipped observations"""
        skipped_observations_counter = 0
        observations_to_insert = []
        for core_row in dwca:
            try:
                obs = build_single_observation(
                    core_row,
                    data_import,
                    hash_datasets=hash_table_datasets,
                    hash_species=hash_table_species,
                )

                if obs is False:
                    skipped_observations_counter = skipped_observations_counter + 1
                else:
                    observations_to_insert.append(obs)
                self.stdout.write(".", ending="")
            except Species.DoesNotExist:
                raise CommandError(f"species not found in db for row: {core_row}")

        # All processed, now insert all observations in one go

        # Bulk create doesn't call save() on the objects, so we need to call set_stable_id() on each object
        self.stdout.write("Setting stable identifiers prior to insertion")
        for obs in observations_to_insert:
            obs.set_stable_id()
        self.stdout.write("Bulk insertion")
        all_observations = Observation.objects.bulk_create(observations_to_insert)
        self.stdout.write("Migrating linked entities")
        for obs in all_observations:
            obs.migrate_linked_entities()

        return skipped_observations_counter

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source-dwca",
            type=argparse.FileType("r"),
            help="Use an existing dwca file as source (otherwise a new GBIF download will be generated and downloaded)",
        )

    def flag_transaction_as_successful(self):
        self.transaction_was_successful = True

    def handle(self, *args, **options) -> None:
        self.stdout.write("(Re)importing all observations")

        # 1. Data preparation / download
        gbif_predicate = None
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
            gbif_predicate = settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"][
                "PREDICATE_BUILDER"
            ](Species.objects.all())

            download_gbif_occurrences(
                gbif_predicate,
                username=settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["USERNAME"],
                password=settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["PASSWORD"],
                output_path=source_data_path,
            )
            self.stdout.write("Observations downloaded")

        self.stdout.write(
            "We now have a (locally accessible) source dwca, real import is starting. We'll use a transaction and put "
            "the website in maintenance mode"
        )

        set_maintenance_mode(True)
        with transaction.atomic():
            transaction.on_commit(self.flag_transaction_as_successful)

            # 2. Create the DataImport object
            current_data_import = DataImport.objects.create(
                start=timezone.now(), gbif_predicate=gbif_predicate
            )
            self.stdout.write(
                f"Created a new DataImport object: #{current_data_import.pk}"
            )

            # 3. Pre-import all the datasets (better here than in a loop that goes over each observation)
            self.stdout.write("Pre-importing all datasets")
            # 3.1 Get all the dataset keys / names from the DwCA
            datasets_referenced_in_dwca = dict()
            with DwCAReader(source_data_path) as dwca:
                for core_row in dwca:
                    gbif_dataset_key = get_string_data(
                        core_row, field_name="http://rs.gbif.org/terms/1.0/datasetKey"
                    )
                    dataset_name = get_string_data(
                        core_row, field_name=qn("datasetName")
                    )
                    datasets_referenced_in_dwca[gbif_dataset_key] = dataset_name

            # 3.2 Fix the empty names (see GBIF bug)
            for dataset_key, dataset_name in datasets_referenced_in_dwca.items():
                if dataset_name == "":
                    datasets_referenced_in_dwca[
                        dataset_key
                    ] = get_dataset_name_from_gbif_api(dataset_key)

            # 3.3 Create/update the Dataset objects
            hash_table_datasets = (
                dict()
            )  # We also create a hash table, so the huge loop below does not need lookups
            for dataset_key, dataset_name in datasets_referenced_in_dwca.items():
                dataset, _ = Dataset.objects.update_or_create(
                    gbif_dataset_key=dataset_key,
                    defaults={"name": dataset_name},
                )
                hash_table_datasets[dataset_key] = dataset

            # 4. We also create a hash table of species, to avoid lookups in the huge loop below
            hash_table_species = dict()
            for species in Species.objects.all():
                hash_table_species[species.gbif_taxon_key] = species

            # 5. Import data from DwCA (observations + GBIF download ID)
            with DwCAReader(source_data_path) as dwca:
                current_data_import.set_gbif_download_id(
                    extract_gbif_download_id_from_dwca(dwca)
                )
                self.stdout.write("Importing all rows")
                current_data_import.skipped_observations_counter = (
                    self._import_all_observations_from_dwca(
                        dwca,
                        current_data_import,
                        hash_table_datasets,
                        hash_table_species,
                    )
                )

            self.stdout.write(
                "All observations imported, now deleting observations linked to previous data imports..."
            )

            # 6. Remove previous observations
            Observation.objects.exclude(data_import=current_data_import).delete()

            # 7. Remove unused Dataset entries (and edit related alerts)
            for dataset in Dataset.objects.all():
                if dataset.observation_set.count() == 0:
                    self.stdout.write(f"Deleting (no longer used) dataset {dataset}")
                    alerts_referencing_dataset = dataset.alert_set.all()
                    if alerts_referencing_dataset.count() > 0:
                        for alert in alerts_referencing_dataset:
                            self.stdout.write(
                                f"We'll first need to un-reference this dataset from alert #{alert}"
                            )
                            alert.datasets.remove(dataset)

                    dataset.delete()

            # 6. Finalize the DataImport object
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
