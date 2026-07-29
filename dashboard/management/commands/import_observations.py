import argparse
import datetime
import json
import logging
import os
import resource
import sys
import tempfile
import time
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone
from dwca.darwincore.utils import qualname as qn  # type: ignore
from dwca.read import DwCAReader  # type: ignore
from gbif_blocking_occurrences_download import download_occurrences as download_gbif_occurrences  # type: ignore
from dashboard.maintenance import (
    disable_maintenance_for_import,
    enable_maintenance_for_import,
)

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

_GBIF = "http://rs.gbif.org/terms/1.0/"

# Terms requested from the DwCA core file, in RawObservationRow field order.
# iter_terms() yields a tuple whose positions match this list exactly, so the
# order here and the unpacking in _raw_from_values must stay in step.
_IMPORT_TERMS = [
    _GBIF + "gbifID",
    qn("occurrenceID"),
    qn("occurrenceStatus"),
    qn("year"),
    qn("month"),
    qn("day"),
    qn("decimalLongitude"),
    qn("decimalLatitude"),
    _GBIF + "datasetKey",
    qn("datasetName"),
    _GBIF + "taxonKey",
    _GBIF + "acceptedTaxonKey",
    _GBIF + "speciesKey",
    qn("basisOfRecord"),
    qn("individualCount"),
    qn("coordinateUncertaintyInMeters"),
    qn("identificationVerificationStatus"),
    qn("locality"),
    qn("municipality"),
    qn("recordedBy"),
    qn("references"),
]

# The discovery pass only ever needed these three. Requesting three terms
# instead of twenty-one, and skipping the RawObservationRow construction
# entirely, makes pass 1 substantially cheaper on a multi-million-row archive.
_DISCOVERY_TERMS = [
    _GBIF + "datasetKey",
    qn("datasetName"),
    qn("basisOfRecord"),
]

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

    Produced by adapters (e.g. ``_raw_from_values``) and consumed by the
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
    taxon_key: str
    accepted_taxon_key: str
    species_key: str
    basis_of_record: str
    individual_count: int | None
    coordinate_uncertainty_in_meters: float | None
    identification_verification_status: str
    locality: str
    municipality: str
    recorded_by: str
    references: str


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _raw_from_values(values: tuple[str, ...]) -> RawObservationRow:
    """Build a RawObservationRow from one iter_terms() tuple.

    ``values`` holds the terms listed in _IMPORT_TERMS, in that order.
    iter_terms() yields raw field values, so the strip() that the previous
    row-based adapter applied via get_string_data is applied here instead.
    """
    (
        gbif_id,
        occurrence_id,
        occurrence_status,
        year,
        month,
        day,
        decimal_longitude,
        decimal_latitude,
        dataset_key,
        dataset_name,
        taxon_key,
        accepted_taxon_key,
        species_key,
        basis_of_record,
        individual_count,
        coordinate_uncertainty_in_meters,
        identification_verification_status,
        locality,
        municipality,
        recorded_by,
        references,
    ) = map(str.strip, values)

    return RawObservationRow(
        gbif_id=int(gbif_id),
        occurrence_id=occurrence_id,
        occurrence_status=occurrence_status,
        year=_int_or_none(year),
        month=_int_or_none(month),
        day=_int_or_none(day),
        decimal_longitude=_float_or_none(decimal_longitude),
        decimal_latitude=_float_or_none(decimal_latitude),
        dataset_key=dataset_key,
        dataset_name=dataset_name,
        taxon_key=taxon_key,
        accepted_taxon_key=accepted_taxon_key,
        species_key=species_key,
        basis_of_record=basis_of_record,
        individual_count=_int_or_none(individual_count),
        coordinate_uncertainty_in_meters=_float_or_none(
            coordinate_uncertainty_in_meters
        ),
        identification_verification_status=identification_verification_status,
        locality=locality,
        municipality=municipality,
        recorded_by=recorded_by,
        references=references,
    )


def species_for_raw(
    raw: RawObservationRow, hash_species: dict[str, Species]
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


def discover_datasets_and_basis_of_record(
    rows: Iterable[tuple[str, str, str]],
) -> tuple[dict[str, str], set[str]]:
    """Walk a row stream once, collecting distinct dataset keys (with their
    names) and distinct basis-of-record values.

    Each element is a (dataset_key, dataset_name, basis_of_record) triple -
    the only three fields this pass ever read. Taking a narrow triple rather
    than a full RawObservationRow lets the DwCA adapter request three terms
    instead of twenty-one.

    Memory is O(distinct datasets + distinct BoR values), never O(rows),
    so this is safe for multi-million-row imports.
    """
    datasets: dict[str, str] = {}
    basis_of_record_values: set[str] = set()
    for dataset_key, dataset_name, basis_of_record in rows:
        datasets[dataset_key] = dataset_name
        if basis_of_record:
            basis_of_record_values.add(basis_of_record)
    return datasets, basis_of_record_values


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


class SkippedObservationException(Exception):
    pass


def build_observation_from_raw(
    raw: RawObservationRow,
    current_data_import: DataImport,
    hash_datasets: dict[str, Dataset],
    hash_species: dict[str, Species],
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

    identification_verification_status_str = raw.identification_verification_status[
        :255
    ]

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


def send_error_import_email(exception: BaseException | None = None):
    body = "An error occurred during the observation data import."
    if exception is not None:
        body += "\n\nThe import was rolled back. Exception traceback:\n\n" + "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
    # fail_silently=False so a delivery problem is surfaced (the caller logs it
    # and still re-raises the original import error) rather than swallowed.
    mail_admins(
        "ERROR during observation data import",
        body,
        fail_silently=False,
    )


def _peak_rss_mb() -> float:
    """Peak resident-set size of this process so far, in MB.

    ru_maxrss is the high-water mark (it only ever grows), so logging it at each
    step shows which step pushed memory highest - the key evidence for locating
    an OOM kill. The unit is platform-dependent: kilobytes on Linux, bytes on
    macOS.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / (1024 * 1024)  # bytes -> MB
    return peak / 1024  # KB -> MB


def _log_with_time(stdout, message: str) -> None:
    """Timestamped log line with peak RSS, suppressed if stdout is None (tests).

    The line is flushed immediately: under an OOM SIGKILL, block-buffered stdout
    (cron/rqworker, not a tty) would otherwise lose the last lines - exactly the
    ones that point at the crashing step.
    """
    if stdout is not None:
        stdout.write(f"{time.ctime()}: {message} [peak RSS: {_peak_rss_mb():.0f} MB]")
        stdout.flush()


def _batch_insert_observations(
    observations_to_insert: list[Observation],
    stdout=None,
) -> None:
    _log_with_time(stdout, "Bulk creation")
    inserted_observations = Observation.objects.bulk_create(observations_to_insert)
    _log_with_time(stdout, "Migrating comments")

    # Optimization: batch-fetch all potential replaced observations in ONE query
    # instead of one query per inserted observation (N+1 problem)
    stable_ids = [obs.stable_id for obs in inserted_observations]
    inserted_obs_pks = {obs.pk for obs in inserted_observations}

    existing_obs_by_stable_id = {}
    for obs in Observation.objects.filter(stable_id__in=stable_ids).exclude(
        pk__in=inserted_obs_pks
    ):
        existing_obs_by_stable_id[obs.stable_id] = obs

    new_obs_ids = []
    replaced_obs_pks = []
    stable_id_to_new_obs = {}

    for obs in inserted_observations:
        if stdout is not None:
            stdout.write("/", ending="")
        replaced_obs = existing_obs_by_stable_id.get(obs.stable_id)
        if replaced_obs is not None:
            replaced_obs_pks.append(replaced_obs.pk)
            stable_id_to_new_obs[obs.stable_id] = obs
        else:
            new_obs_ids.append(obs.id)

    # Batch migrate comments in ONE update query (no need to load comments into memory)
    from dashboard.models import ObservationComment

    if replaced_obs_pks:
        for old_obs in Observation.objects.filter(pk__in=replaced_obs_pks):
            new_obs = stable_id_to_new_obs.get(old_obs.stable_id)
            if new_obs:
                ObservationComment.objects.filter(observation=old_obs).update(
                    observation=new_obs
                )

    _log_with_time(stdout, "Creating unseen observations for new observations")
    create_unseen_observations(Observation.objects.filter(id__in=new_obs_ids))


def _import_all_observations(
    raw_rows: Iterable[RawObservationRow],
    data_import: DataImport,
    hash_table_datasets: dict[str, Dataset],
    hash_table_species: dict[str, Species],
    hash_table_basis_of_record: dict[str, BasisOfRecord],
    hash_table_verification_status: dict[str, bool],
    stdout=None,
) -> int:
    """Stream rows into the DB in chunks of BULK_CREATE_CHUNK_SIZE.

    Returns the number of skipped observations.
    """
    skipped_observations_counter = 0
    observations_to_insert: list[Observation] = []

    for index, raw_row in enumerate(raw_rows):
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
            if stdout is not None:
                stdout.write(".", ending="")
        except KeyError:
            raise CommandError(f"species not found in db for raw row: {raw_row}")
        except SkippedObservationException:
            skipped_observations_counter += 1
            if stdout is not None:
                stdout.write("x", ending="")

        if index > 0 and index % BULK_CREATE_CHUNK_SIZE == 0:
            _log_with_time(stdout, "Bulk size reached...")
            _batch_insert_observations(observations_to_insert, stdout=stdout)
            observations_to_insert = []

    # Insert the last chunk
    if observations_to_insert:
        _batch_insert_observations(observations_to_insert, stdout=stdout)

    return skipped_observations_counter


def _vacuum_analyze_rewritten_tables(stdout) -> None:
    """VACUUM ANALYZE the two tables the import rewrites wholesale.

    The import replaces every observation row (and, through
    ``migrate_unseen_observations``, most of the unseen table), so on commit
    both tables hold as many dead tuples as live ones and their visibility maps
    still describe the *previous* dataset. Until something vacuums them, an
    index-only scan has to fall back to a heap fetch per index entry: measured
    on a 100k-row import, the observations histogram did 199970 heap fetches
    and touched ~200k buffers (85 ms), against 0 heap fetches and 773 buffers
    (22 ms) once vacuumed. Waiting for autovacuum leaves that regression in
    place for however long it takes to get round to a freshly rewritten table.

    Cost is small next to the import itself: ~0.9 s for the observations table
    and ~0.15 s for the unseen table per 100k observations.

    Runs outside the import transaction, because VACUUM cannot run inside one,
    and after maintenance mode has been lifted - so it competes with live
    traffic rather than extending the outage.
    """
    if connection.in_atomic_block:
        # Nothing to do rather than a hard failure: this happens when the
        # command is driven from inside a transaction (a plain Django TestCase,
        # or a caller wrapping it in atomic()), where a rollback discards the
        # rewrite anyway.
        _log_with_time(stdout, "Skipping VACUUM ANALYZE: running inside a transaction.")
        return

    for table in ("dashboard_observation", "dashboard_observationunseen"):
        try:
            with connection.cursor() as cursor:
                # Table names are literals, never user input.
                cursor.execute(f"VACUUM (ANALYZE) {table}")
            _log_with_time(stdout, f"VACUUM ANALYZE done on {table}")
        except Exception as exc:
            # The import is already committed and the site is back up, so a
            # vacuum problem (e.g. the DB user does not own the table) must not
            # fail the command: autovacuum will get there eventually.
            _log_with_time(stdout, f"VACUUM ANALYZE failed on {table}: {exc!r}")


def run_import(
    raw_rows_factory: Callable[[], Iterable[RawObservationRow]],
    discovery_rows_factory: Callable[[], Iterable[tuple[str, str, str]]],
    *,
    gbif_download_id: str | None = None,
    gbif_predicate: dict | None = None,
    stdout=None,
) -> DataImport:
    """Run the transactional observation-import pipeline.

    ``discovery_rows_factory`` feeds pass 1 (dataset / basis-of-record
    discovery) with (dataset_key, dataset_name, basis_of_record) triples;
    ``raw_rows_factory`` feeds pass 2, which builds and inserts observations.
    Each call must return a fresh iterable. This preserves streaming for
    multi-million-row imports: no row is held in memory across passes.

    Maintenance mode is enabled for the duration of the import and always
    cleared on exit, whether the import succeeds or fails. On failure the
    transaction rolls back (leaving the database unchanged) and an admin email
    with the exception traceback is sent before the error is re-raised; on
    success an admin email is sent.
    """
    _log_with_time(
        stdout,
        "Real import is starting. We'll use a transaction and put the website in maintenance mode",
    )

    enable_maintenance_for_import()
    try:
        with transaction.atomic():
            current_data_import = DataImport.objects.create(
                start=timezone.now(), gbif_predicate=gbif_predicate
            )
            _log_with_time(
                stdout, f"Created a new DataImport object: #{current_data_import.pk}"
            )

            # Pass 1: discover datasets + basis-of-record values
            _log_with_time(
                stdout, "3. Pre-importing all datasets and basis of record values"
            )
            _log_with_time(
                stdout,
                "3.1 Scanning rows to get the dataset keys and basis of record values",
            )
            (
                datasets_referenced,
                bor_values_referenced,
            ) = discover_datasets_and_basis_of_record(discovery_rows_factory())

            _log_with_time(stdout, "3.3 Creating/updating the Dataset objects")
            hash_table_datasets: dict[str, Dataset] = {}
            for dataset_key, dataset_name in datasets_referenced.items():
                _log_with_time(stdout, f"Creating/updating dataset {dataset_key}")
                dataset, _ = Dataset.objects.update_or_create(
                    gbif_dataset_key=dataset_key,
                    defaults={"name": dataset_name},
                )
                hash_table_datasets[dataset_key] = dataset

            _log_with_time(stdout, "3.4 Creating/getting the BasisOfRecord objects")
            hash_table_basis_of_record: dict[str, BasisOfRecord] = {}
            for bor_value in bor_values_referenced:
                bor, _ = BasisOfRecord.objects.get_or_create(name=bor_value)
                hash_table_basis_of_record[bor_value] = bor

            _log_with_time(stdout, "4. Creating a hash table of species")
            hash_table_species: dict[str, Species] = {
                species.gbif_col_taxon_key: species
                for species in Species.objects.all()
                if species.gbif_col_taxon_key
            }

            _log_with_time(stdout, "5. Building verification status hash")
            hash_table_verification_status = load_verification_status_hash()

            if gbif_download_id is not None:
                current_data_import.set_gbif_download_id(gbif_download_id)

            # Pass 2: build and insert observations
            _log_with_time(stdout, "Importing all rows")
            current_data_import.skipped_observations_counter = _import_all_observations(
                raw_rows_factory(),
                current_data_import,
                hash_table_datasets=hash_table_datasets,
                hash_table_species=hash_table_species,
                hash_table_basis_of_record=hash_table_basis_of_record,
                hash_table_verification_status=hash_table_verification_status,
                stdout=stdout,
            )

            _log_with_time(stdout, "All observations imported")

            _log_with_time(stdout, "Migrating unseen observations")
            migrate_unseen_observations(current_data_import)

            _log_with_time(
                stdout, "now deleting observations linked to previous data imports..."
            )
            Observation.objects.exclude(data_import=current_data_import).delete()
            _log_with_time(stdout, "Previous observations deleted")

            _log_with_time(
                stdout,
                "We'll now create or refresh the materialized views. This can take a while.",
            )
            create_or_refresh_materialized_views(
                zoom_levels=[settings.ZOOM_LEVEL_FOR_MIN_MAX_QUERY]
            )

            # Remove unused Dataset entries (and edit related alerts)
            empty_datasets = (
                Dataset.objects.annotate(obs_count=Count("observation"))
                .filter(obs_count=0)
                .prefetch_related("alert_set")
            )
            for dataset in empty_datasets:
                _log_with_time(stdout, f"Deleting (no longer used) dataset {dataset}")
                alerts_referencing_dataset = dataset.alert_set.all()  # type: ignore[attr-defined]  # Prefetched; annotate() drops the model type
                if alerts_referencing_dataset:
                    for alert in alerts_referencing_dataset:
                        _log_with_time(
                            stdout,
                            f"We'll first need to un-reference this dataset from alert #{alert}",
                        )
                        alert.datasets.remove(dataset)
                dataset.delete()

            # Remove unused BasisOfRecord entries (and edit related alerts)
            empty_basis_of_records = (
                BasisOfRecord.objects.annotate(obs_count=Count("observation"))
                .filter(obs_count=0)
                .prefetch_related("alert_set")
            )
            for bor in empty_basis_of_records:
                _log_with_time(
                    stdout, f"Deleting (no longer used) basis of record {bor}"
                )
                alerts_referencing_bor = bor.alert_set.all()  # type: ignore[attr-defined]  # Prefetched; annotate() drops the model type
                if alerts_referencing_bor:
                    for alert in alerts_referencing_bor:
                        _log_with_time(
                            stdout,
                            f"We'll first need to un-reference this basis of record from alert #{alert}",
                        )
                        alert.basis_of_record_filters.remove(bor)
                bor.delete()

            _log_with_time(stdout, "Updating the DataImport object")
            current_data_import.complete()
            _log_with_time(stdout, "Committing the transaction")

        _log_with_time(stdout, "Transaction committed")
    except Exception as exc:
        # The import failed and the transaction rolled back, so the database is
        # unchanged. Notify the admins with the traceback before re-raising:
        # the failure must be visible (no silent failures) and the scheduled
        # job must exit non-zero. Guard the email send so a mail problem can
        # neither mask the original error nor skip the maintenance reset below.
        _log_with_time(stdout, f"Import failed ({exc!r}); notifying admins.")
        try:
            send_error_import_email(exc)
        except Exception as mail_exc:
            _log_with_time(
                stdout, f"Could not send the import-error email: {mail_exc!r}"
            )
        raise
    finally:
        # Always leave maintenance mode, even if the import raised. The work
        # above runs in a single transaction that rolls back on failure, so a
        # failed import leaves the database unchanged - there is no
        # half-imported state to protect by staying in maintenance. Leaving it
        # ON on failure would only turn a transient import error into a site
        # outage needing manual recovery (observed in production: a crashing
        # import stranded the site in maintenance mode).
        _log_with_time(stdout, "Leaving maintenance mode.")
        disable_maintenance_for_import()

    # After the transaction and after maintenance mode is lifted: the table was
    # just rewritten, so its visibility map and statistics are stale.
    _log_with_time(stdout, "Vacuuming and analyzing the rewritten tables")
    _vacuum_analyze_rewritten_tables(stdout)

    _log_with_time(stdout, "Sending success report")
    send_successful_import_email()
    return current_data_import


class Command(BaseCommand):
    help = (
        "Import new observations and delete previous ones. "
        ""
        "By default, a new download is generated at GBIF. "
        "The --source-dwca option can be used to provide an existing local file instead."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source-dwca",
            type=argparse.FileType("r"),
            help="Use an existing dwca file as source (otherwise a new GBIF download will be generated and downloaded)",
        )

    def handle(self, *args, **options) -> None:
        start_time = time.time()

        # Allow the verbosity option for our custom logging
        # (see https://reinout.vanrees.org/weblog/2017/03/08/logging-verbosity-managment-commands.html)
        verbosity = int(options["verbosity"])
        root_logger = logging.getLogger("")
        if verbosity > 1:
            root_logger.setLevel(logging.DEBUG)

        _log_with_time(self.stdout, "(Re)importing all observations")

        # Preflight: every species must have a COL XR key, otherwise the
        # download predicate is broken/empty and occurrences cannot be matched.
        # All-or-nothing on purpose - a missing key would silently drop a
        # species from monitoring. Blocks before any download is triggered.
        # A blank ("") key counts as missing too, not just NULL: it would pass a
        # NULL-only check, then be dropped from the match hash and inject an
        # empty value into the download predicate.
        missing = list(
            Species.objects.filter(
                Q(gbif_col_taxon_key__isnull=True) | Q(gbif_col_taxon_key="")
            ).order_by("name")
        )
        if missing:
            names = ", ".join(f"{s.name} ({s.gbif_taxon_key})" for s in missing)
            raise CommandError(
                "Cannot import: these species have no gbif_col_taxon_key: "
                f"{names}. Run `manage.py convert_taxon_keys_to_col` (and curate "
                "any unresolved species in the admin) before importing."
            )

        # 1. Resolve DwCA source (existing file or trigger a new GBIF download)
        gbif_predicate: dict | None = None
        tmp_source_path: str | None = None
        if options["source_dwca"]:
            _log_with_time(self.stdout, "Using a user-provided DWCA file")
            source_data_path = options["source_dwca"].name
        else:
            _log_with_time(
                self.stdout,
                "No DWCA file provided, we'll generate and get a new GBIF download",
            )
            _log_with_time(
                self.stdout,
                "Triggering a GBIF download and waiting for it - this can be long...",
            )

            tmp_file = tempfile.NamedTemporaryFile(delete=False)
            source_data_path = tmp_file.name
            tmp_source_path = source_data_path
            tmp_file.close()
            # This might take several minutes...
            gbif_predicate = settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"][
                "PREDICATE_BUILDER"
            ](Species.objects.all())
            _log_with_time(
                self.stdout,
                f"GBIF predicate sent to the download API: {json.dumps(gbif_predicate)}",
            )

            # The download library reports progress (the download_id GBIF returns,
            # each retry, and any non-200 status) via the root logger at INFO, which
            # is swallowed at the default verbosity - so the GBIF exchange is normally
            # invisible. Bridge it to our stdout for the duration of the download so we
            # can confirm the predicate produced a real download (and not, say, an auth
            # or quota error), then restore the previous logging state.
            gbif_handler = logging.StreamHandler(sys.stdout)
            gbif_handler.setFormatter(
                logging.Formatter("%(asctime)s: GBIF download: %(message)s")
            )
            previous_root_level = root_logger.level
            root_logger.addHandler(gbif_handler)
            if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
                root_logger.setLevel(logging.INFO)
            try:
                download_gbif_occurrences(
                    gbif_predicate,
                    username=settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["USERNAME"],
                    password=settings.GBIF_ALERT["GBIF_DOWNLOAD_CONFIG"]["PASSWORD"],
                    output_path=source_data_path,
                )
            finally:
                root_logger.removeHandler(gbif_handler)
                root_logger.setLevel(previous_root_level)
            _log_with_time(self.stdout, "Observations downloaded")

        # 2. Extract gbif_download_id from DwCA metadata (only needs to read metadata)
        _log_with_time(self.stdout, "Opening DWCA to read metadata")
        with DwCAReader(source_data_path) as dwca:
            gbif_download_id = extract_gbif_download_id_from_dwca(dwca)
        _log_with_time(
            self.stdout, f"GBIF download id read from DWCA metadata: {gbif_download_id}"
        )

        # 3. Build a fresh-generator factory that lazily streams rows
        def raw_rows_factory() -> Iterable[RawObservationRow]:
            # A generator function, so each call returns a fresh iterator, and
            # the reader is closed when the pass ends. The previous generator
            # expression never closed its DwCAReader.
            # Metadata was already read at step 2 by its own reader; parsing the
            # EML again on each row pass is wasted work.
            with DwCAReader(source_data_path, skip_metadata=True) as dwca:
                for values in dwca.iter_terms(_IMPORT_TERMS):
                    yield _raw_from_values(values)

        def discovery_rows_factory() -> Iterable[tuple[str, str, str]]:
            with DwCAReader(source_data_path, skip_metadata=True) as dwca:
                for dataset_key, dataset_name, basis_of_record in dwca.iter_terms(
                    _DISCOVERY_TERMS
                ):
                    yield (
                        dataset_key.strip(),
                        dataset_name.strip(),
                        basis_of_record.strip(),
                    )

        # 4. Run the transactional pipeline
        run_import(
            raw_rows_factory,
            discovery_rows_factory,
            gbif_download_id=gbif_download_id,
            gbif_predicate=gbif_predicate,
            stdout=self.stdout,
        )

        # 5. Clean up the temporary DwCA (only if we downloaded it ourselves)
        if tmp_source_path is not None:
            _log_with_time(self.stdout, "Deleting the (temporary) source DWCA file")
            os.unlink(tmp_source_path)

        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        _log_with_time(
            self.stdout,
            f"Import observations process successfully completed in {elapsed_minutes}m {elapsed_seconds}s",
        )
