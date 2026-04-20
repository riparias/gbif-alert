import argparse
import datetime
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from dwca.darwincore.utils import qualname as qn  # type: ignore
from dwca.read import DwCAReader  # type: ignore
from dwca.rows import CoreRow  # type: ignore
from gbif_blocking_occurrences_download import download_occurrences as download_gbif_occurrences  # type: ignore
from maintenance_mode.core import set_maintenance_mode  # type: ignore

from dashboard.models import (
    Species,
    Observation,
    DataImport,
    Dataset,
    BasisOfRecord,
    create_unseen_observations,
    migrate_unseen_observations,
)
from dashboard.views.helpers import (
    create_or_refresh_materialized_views,
)

BULK_CREATE_CHUNK_SIZE = 10000

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_VERIFICATION_STATUS_JSON = os.path.join(
    _THIS_DIR, "..", "..", "verification_status_classification.json"
)


def load_verification_status_hash() -> dict[str, bool]:
    """Load verification_status_classification.json into a dict mapping status string -> verified bool."""
    with open(_VERIFICATION_STATUS_JSON, encoding="utf-8") as f:
        entries = json.load(f)
    return {entry["key"]: entry["verified"] for entry in entries}


@dataclass(frozen=True)
class RawObservationRow:
    """Format-agnostic representation of a single observation row.

    Produced by adapters (e.g. ``dwca_row_to_raw``) and consumed by the
    import pipeline. Unparseable numeric fields are represented as ``None``
    so the business logic (not the adapter) owns the skip-vs-default
    decision.
    """

    gbif_id: int
    occurrence_id: str
    occurrence_status: str
    year: int | None
    month: int | None
    day: int | None
    decimal_longitude: float | None
    decimal_latitude: float | None
    dataset_key: str
    dataset_name: str
    taxon_key: int
    accepted_taxon_key: int
    species_key: int
    basis_of_record: str
    individual_count: int | None
    coordinate_uncertainty_in_meters: float | None
    identification_verification_status: str
    locality: str
    municipality: str
    recorded_by: str
    references: str


def _get_int_or_none(row: CoreRow, field_name: str) -> int | None:
    try:
        return int(get_string_data(row, field_name=field_name))
    except ValueError:
        return None


def _get_float_or_none(row: CoreRow, field_name: str) -> float | None:
    try:
        return float(get_string_data(row, field_name=field_name))
    except ValueError:
        return None


def dwca_row_to_raw(row: CoreRow) -> RawObservationRow:
    """Convert a DwCA CoreRow into a typed RawObservationRow."""
    return RawObservationRow(
        gbif_id=int(
            get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/gbifID")
        ),
        occurrence_id=get_string_data(row, field_name=qn("occurrenceID")),
        occurrence_status=get_string_data(row, field_name=qn("occurrenceStatus")),
        year=_get_int_or_none(row, qn("year")),
        month=_get_int_or_none(row, qn("month")),
        day=_get_int_or_none(row, qn("day")),
        decimal_longitude=_get_float_or_none(row, qn("decimalLongitude")),
        decimal_latitude=_get_float_or_none(row, qn("decimalLatitude")),
        dataset_key=get_string_data(
            row, field_name="http://rs.gbif.org/terms/1.0/datasetKey"
        ),
        dataset_name=get_string_data(row, field_name=qn("datasetName")),
        taxon_key=int(
            get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/taxonKey")
        ),
        accepted_taxon_key=int(
            get_string_data(
                row, field_name="http://rs.gbif.org/terms/1.0/acceptedTaxonKey"
            )
        ),
        species_key=int(
            get_string_data(row, field_name="http://rs.gbif.org/terms/1.0/speciesKey")
        ),
        basis_of_record=get_string_data(row, field_name=qn("basisOfRecord")),
        individual_count=_get_int_or_none(row, qn("individualCount")),
        coordinate_uncertainty_in_meters=_get_float_or_none(
            row, qn("coordinateUncertaintyInMeters")
        ),
        identification_verification_status=get_string_data(
            row, field_name=qn("identificationVerificationStatus")
        ),
        locality=get_string_data(row, field_name=qn("locality")),
        municipality=get_string_data(row, field_name=qn("municipality")),
        recorded_by=get_string_data(row, field_name=qn("recordedBy")),
        references=get_string_data(row, field_name=qn("references")),
    )


def species_for_raw(
    raw: RawObservationRow, hash_species: dict[int, Species]
) -> Species:
    """Look up a Species from a RawObservationRow.

    Tries taxon_key first, falls back to accepted_taxon_key, then species_key.
    Raises KeyError if none match.
    """
    try:
        return hash_species[raw.taxon_key]
    except KeyError:
        try:
            return hash_species[raw.accepted_taxon_key]
        except KeyError:
            return hash_species[raw.species_key]


def extract_gbif_download_id_from_dwca(dwca: DwCAReader) -> str:
    e = dwca.metadata.find("dataset").find("alternateIdentifier")
    # As of 2025-03-13, GBIF has changed the field name...
    # This new adjustment is untested
    if e is not None:
        return e.text
    else:
        return (
            dwca.metadata.find("additionalMetadata")
            .find("metadata")
            .find("gbif")
            .find("citation")
            .get("identifier")
        )


def get_string_data(row: CoreRow, field_name: str) -> str:
    """Extract string data from a row (with minor cleanup)"""
    return row.data[field_name].strip()


class SkippedObservationException(Exception):
    pass


def build_observation_from_raw(
    raw: RawObservationRow,
    current_data_import: DataImport,
    hash_datasets: dict[str, Dataset],
    hash_species: dict[int, Species],
    hash_basis_of_record: dict[str, BasisOfRecord],
    hash_verification_status: dict[str, bool],
) -> Observation:
    """Build an Observation from a RawObservationRow.

    Raises SkippedObservationException when the row is unusable (missing
    year, missing coordinates, missing occurrence_id, or occurrence_status
    other than "PRESENT"). Missing month/day default to 1.

    Raises KeyError if the species referenced cannot be found.
    """
    if (
        raw.year is None
        or raw.decimal_longitude is None
        or raw.decimal_latitude is None
        or raw.occurrence_id == ""
        or raw.occurrence_status != "PRESENT"
    ):
        raise SkippedObservationException()

    # Some dates are incomplete, we're good as long as we have a year
    month = raw.month if raw.month is not None else 1
    day = raw.day if raw.day is not None else 1
    date = datetime.date(raw.year, month, day)

    point = Point(raw.decimal_longitude, raw.decimal_latitude, srid=4326)

    identification_verification_status_str = raw.identification_verification_status[:255]

    new_observation = Observation(
        gbif_id=raw.gbif_id,
        occurrence_id=raw.occurrence_id,
        species=species_for_raw(raw, hash_species),
        location=point,
        date=date,
        data_import=current_data_import,
        source_dataset=hash_datasets[raw.dataset_key],
        individual_count=raw.individual_count,
        locality=raw.locality,
        municipality=raw.municipality,
        basis_of_record=hash_basis_of_record[raw.basis_of_record],
        identification_verification_status=identification_verification_status_str,
        verified=hash_verification_status.get(
            identification_verification_status_str, False
        ),
        recorded_by=raw.recorded_by,
        coordinate_uncertainty_in_meters=raw.coordinate_uncertainty_in_meters,
        references=raw.references,
    )
    new_observation.set_or_migrate_initial_data_import(
        current_data_import=current_data_import
    )

    # We'll use bulk_create() later, so we need to call set_stable_id() on each object
    new_observation.set_stable_id()
    return new_observation


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

    def log_with_time(self, message: str):
        self.stdout.write(f"{time.ctime()}: {message}")

    def _import_all_observations_from_dwca(
        self,
        dwca: DwCAReader,
        data_import: DataImport,
        hash_table_datasets: dict,
        hash_table_species: dict,
        hash_table_basis_of_record: dict,
        hash_table_verification_status: dict[str, bool],
    ) -> int:
        """:return the number of skipped observations"""
        skipped_observations_counter = 0

        observations_to_insert = []
        for index, core_row in enumerate(dwca):
            raw_row = dwca_row_to_raw(core_row)
            try:
                obs = build_observation_from_raw(
                    raw_row,
                    data_import,
                    hash_datasets=hash_table_datasets,
                    hash_species=hash_table_species,
                    hash_basis_of_record=hash_table_basis_of_record,
                    hash_verification_status=hash_table_verification_status,
                )
                observations_to_insert.append(obs)
                self.stdout.write(".", ending="")
            except KeyError:
                raise CommandError(f"species not found in db for row: {core_row}")
            except SkippedObservationException:
                skipped_observations_counter = skipped_observations_counter + 1
                self.stdout.write("x", ending="")

            if index > 0 and index % BULK_CREATE_CHUNK_SIZE == 0:
                self.log_with_time("Bulk size reached...")
                self.batch_insert_observations(observations_to_insert)
                observations_to_insert = []

        # Insert the last chunk
        if observations_to_insert:
            self.batch_insert_observations(observations_to_insert)

        return skipped_observations_counter

    def batch_insert_observations(self, observations_to_insert: list[Observation]):
        self.log_with_time("Bulk creation")
        inserted_observations = Observation.objects.bulk_create(observations_to_insert)
        self.log_with_time("Migrating comments")

        # Optimization: batch-fetch all potential replaced observations in ONE query
        # instead of one query per inserted observation (N+1 problem)
        stable_ids = [obs.stable_id for obs in inserted_observations]
        inserted_obs_pks = {obs.pk for obs in inserted_observations}

        # Find all existing observations with matching stable_ids (excluding newly inserted ones)
        existing_obs_by_stable_id = {}
        for obs in Observation.objects.filter(stable_id__in=stable_ids).exclude(
            pk__in=inserted_obs_pks
        ):
            existing_obs_by_stable_id[obs.stable_id] = obs

        # Build mapping from new observations to replaced observations
        new_obs_ids = []
        replaced_obs_pks = []
        stable_id_to_new_obs = {}

        for obs in inserted_observations:
            self.stdout.write("/", ending="")
            replaced_obs = existing_obs_by_stable_id.get(obs.stable_id)
            if replaced_obs is not None:
                replaced_obs_pks.append(replaced_obs.pk)
                stable_id_to_new_obs[obs.stable_id] = obs
            else:
                new_obs_ids.append(obs.id)

        # Batch migrate comments in ONE update query (no need to load comments into memory)
        from dashboard.models import ObservationComment

        if replaced_obs_pks:
            # For each comment on a replaced observation, update it to point to the new one
            for old_obs in Observation.objects.filter(pk__in=replaced_obs_pks):
                new_obs = stable_id_to_new_obs.get(old_obs.stable_id)
                if new_obs:
                    ObservationComment.objects.filter(observation=old_obs).update(
                        observation=new_obs
                    )

        self.log_with_time("Creating unseen observations for new observations")
        create_unseen_observations(Observation.objects.filter(id__in=new_obs_ids))

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source-dwca",
            type=argparse.FileType("r"),
            help="Use an existing dwca file as source (otherwise a new GBIF download will be generated and downloaded)",
        )

    def flag_transaction_as_successful(self):
        self.transaction_was_successful = True

    def handle(self, *args, **options) -> None:
        start_time = time.time()

        # Allow the verbosity option for our custom logging
        # (see https://reinout.vanrees.org/weblog/2017/03/08/logging-verbosity-managment-commands.html)
        verbosity = int(options["verbosity"])
        root_logger = logging.getLogger("")
        if verbosity > 1:
            root_logger.setLevel(logging.DEBUG)

        self.log_with_time("(Re)importing all observations")

        # 1. Data preparation / download
        gbif_predicate = None
        if options["source_dwca"]:
            self.log_with_time("Using a user-provided DWCA file")
            source_data_path = options["source_dwca"].name
        else:
            self.log_with_time(
                "No DWCA file provided, we'll generate and get a new GBIF download"
            )
            self.log_with_time(
                "Triggering a GBIF download and waiting for it - this can be long..."
            )

            tmp_file = tempfile.NamedTemporaryFile(delete=False)
            source_data_path = tmp_file.name
            tmp_file.close()
            # This might take several minutes...
            gbif_predicate = settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"][
                "PREDICATE_BUILDER"
            ](Species.objects.all())

            download_gbif_occurrences(
                gbif_predicate,
                username=settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["USERNAME"],
                password=settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["PASSWORD"],
                output_path=source_data_path,
            )
            self.log_with_time("Observations downloaded")

        self.log_with_time(
            "We now have a (locally accessible) source dwca, real import is starting. We'll use a transaction and put the website in maintenance mode"
        )

        set_maintenance_mode(True)
        with transaction.atomic():
            transaction.on_commit(self.flag_transaction_as_successful)

            # 2. Create the DataImport object
            current_data_import = DataImport.objects.create(
                start=timezone.now(), gbif_predicate=gbif_predicate
            )
            self.log_with_time(
                f"Created a new DataImport object: #{current_data_import.pk}"
            )

            # 3. Pre-import all the datasets and basis of record values
            self.log_with_time(
                "3. Pre-importing all datasets and basis of record values"
            )
            # 3.1 Get all the dataset keys / names and basis of record values from the DwCA
            datasets_referenced_in_dwca = dict()
            basis_of_record_values_in_dwca: set[str] = set()
            self.log_with_time(
                "3.1 Reading the DwCA to get the dataset keys and basis of record values"
            )
            with DwCAReader(source_data_path) as dwca:
                for core_row in dwca:
                    gbif_dataset_key = get_string_data(
                        core_row, field_name="http://rs.gbif.org/terms/1.0/datasetKey"
                    )
                    dataset_name = get_string_data(
                        core_row, field_name=qn("datasetName")
                    )
                    datasets_referenced_in_dwca[gbif_dataset_key] = dataset_name

                    basis_of_record_value = get_string_data(
                        core_row, field_name=qn("basisOfRecord")
                    )
                    if basis_of_record_value:
                        basis_of_record_values_in_dwca.add(basis_of_record_value)

            # 3.2 Fix the empty names (see GBIF bug)
            # self.log_with_time("3.2 Fixing empty dataset names")
            # TODO: uncomment this after GBIF outage
            # for dataset_key, dataset_name in datasets_referenced_in_dwca.items():
            #     if dataset_name == "":
            #         datasets_referenced_in_dwca[
            #             dataset_key
            #         ] = get_dataset_name_from_gbif_api(dataset_key)

            # 3.3 Create/update the Dataset objects
            self.log_with_time("3.3 Creating/updating the Dataset objects")
            hash_table_datasets = (
                dict()
            )  # We also create a hash table, so the huge loop below does not need lookups
            for dataset_key, dataset_name in datasets_referenced_in_dwca.items():
                self.log_with_time(f"Creating/updating dataset {dataset_key}")
                dataset, _ = Dataset.objects.update_or_create(
                    gbif_dataset_key=dataset_key,
                    defaults={"name": dataset_name},
                )
                hash_table_datasets[dataset_key] = dataset

            # 3.4 Creating/getting the BasisOfRecord objects
            self.log_with_time("3.4 Creating/getting the BasisOfRecord objects")
            hash_table_basis_of_record: dict[str, BasisOfRecord] = dict()
            for bor_value in basis_of_record_values_in_dwca:
                bor, _ = BasisOfRecord.objects.get_or_create(name=bor_value)
                hash_table_basis_of_record[bor_value] = bor

            # 4. We also create a hash table of species, to avoid lookups in the huge loop below
            self.log_with_time("4. Creating a hash table of species")
            hash_table_species = dict()
            for species in Species.objects.all():
                hash_table_species[species.gbif_taxon_key] = species

            # 5. Build verification status hash and import data from DwCA
            self.log_with_time("5. Building verification status hash")
            hash_table_verification_status = load_verification_status_hash()

            with DwCAReader(source_data_path) as dwca:
                current_data_import.set_gbif_download_id(
                    extract_gbif_download_id_from_dwca(dwca)
                )
                self.log_with_time("Importing all rows")
                current_data_import.skipped_observations_counter = (
                    self._import_all_observations_from_dwca(
                        dwca,
                        current_data_import,
                        hash_table_datasets,
                        hash_table_species,
                        hash_table_basis_of_record,
                        hash_table_verification_status,
                    )
                )

            self.log_with_time("All observations imported")

            # Migrate the unseen objects, or delete them if they are not relevant anymore
            self.log_with_time("Migrating unseen observations")
            migrate_unseen_observations(current_data_import)

            self.log_with_time(
                "now deleting observations linked to previous data imports..."
            )
            # 6. Remove previous observations
            Observation.objects.exclude(data_import=current_data_import).delete()
            self.log_with_time("Previous observations deleted")

            self.log_with_time(
                "We'll now create or refresh the materialized views. This can take a while."
            )

            # 7. Create or refresh the materialized view (for the map)
            create_or_refresh_materialized_views(
                zoom_levels=[settings.ZOOM_LEVEL_FOR_MIN_MAX_QUERY]
            )

            # 8. Remove unused Dataset entries (and edit related alerts)
            # Optimization: use annotation to find empty datasets in ONE query
            empty_datasets = (
                Dataset.objects.annotate(obs_count=Count("observation"))
                .filter(obs_count=0)
                .prefetch_related("alert_set")
            )

            for dataset in empty_datasets:
                self.log_with_time(f"Deleting (no longer used) dataset {dataset}")

                alerts_referencing_dataset = dataset.alert_set.all()  # Prefetched
                if alerts_referencing_dataset:
                    for alert in alerts_referencing_dataset:
                        self.log_with_time(
                            f"We'll first need to un-reference this dataset from alert #{alert}"
                        )
                        alert.datasets.remove(dataset)

                dataset.delete()

            # 8b. Remove unused BasisOfRecord entries (and edit related alerts)
            empty_basis_of_records = (
                BasisOfRecord.objects.annotate(obs_count=Count("observation"))
                .filter(obs_count=0)
                .prefetch_related("alert_set")
            )

            for bor in empty_basis_of_records:
                self.log_with_time(f"Deleting (no longer used) basis of record {bor}")

                alerts_referencing_bor = bor.alert_set.all()  # Prefetched
                if alerts_referencing_bor:
                    for alert in alerts_referencing_bor:
                        self.log_with_time(
                            f"We'll first need to un-reference this basis of record from alert #{alert}"
                        )
                        alert.basis_of_record_filters.remove(bor)

                bor.delete()

            # 9. Finalize the DataImport object
            self.log_with_time("Updating the DataImport object")

            current_data_import.complete()
            if options["source_dwca"] is None:
                self.log_with_time("Deleting the (temporary) source DWCA file")
                os.unlink(source_data_path)
            self.log_with_time("Committing the transaction")

        self.log_with_time("Transaction committed")
        self.log_with_time("Leaving maintenance mode.")
        set_maintenance_mode(False)

        self.log_with_time("Sending email report")
        if self.transaction_was_successful:
            send_successful_import_email()
        else:
            send_error_import_email()

        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        self.log_with_time(
            f"Import observations process successfully completed in {elapsed_minutes}m {elapsed_seconds}s"
        )
