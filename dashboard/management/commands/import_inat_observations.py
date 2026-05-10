"""
Management command: import_inat_observations

Imports observations from the iNaturalist API for all species in the database
that have an inat_taxon_id set. Filters by the configured place_id and
quality grades. Operates independently of the GBIF import pipeline — only
iNaturalist observations from previous imports are replaced; GBIF observations
are untouched.

Run sync_inat_taxon_ids before the first execution.
"""

import logging
import time

from django.conf import settings
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from maintenance_mode.core import set_maintenance_mode  # type: ignore

from dashboard.inat_api import get_observations, InatApiError, _parse_location_from_obs
from dashboard.models import (
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    Species,
    create_unseen_observations,
    migrate_unseen_observations,
)
from dashboard.views.helpers import create_or_refresh_materialized_views

logger = logging.getLogger(__name__)

BULK_CREATE_CHUNK_SIZE = 10000
INAT_DATASET_KEY = "inat"
INAT_DATASET_NAME = "iNaturalist"
INAT_BASIS_OF_RECORD = "HUMAN_OBSERVATION"


def _parse_date(obs: dict):
    """Return a date from observed_on, or None if missing/invalid."""
    import datetime

    observed_on = obs.get("observed_on")
    if not observed_on:
        return None
    try:
        return datetime.date.fromisoformat(observed_on)
    except ValueError:
        return None


def build_observation_from_inat(
    inat_obs: dict,
    current_data_import: DataImport,
    inat_dataset: Dataset,
    species: Species,
    basis_of_record: BasisOfRecord,
) -> Observation | None:
    """
    Map a raw iNat API observation dict to an Observation model instance.

    Returns None if the observation lacks a date (required field).
    """
    obs_date = _parse_date(inat_obs)
    if obs_date is None:
        return None

    uuid = inat_obs.get("uuid") or ""
    if not uuid:
        # Every iNat observation should have a UUID; skip rather than create a collision-prone row
        logger.warning(
            "iNat observation id=%s has no uuid, skipping", inat_obs.get("id")
        )
        return None

    quality_grade = inat_obs.get("quality_grade", "")

    obs = Observation(
        source=Observation.SOURCE_INAT,
        inat_id=inat_obs["id"],
        gbif_id="",
        occurrence_id=uuid,
        species=species,
        location=_parse_location_from_obs(inat_obs),
        date=obs_date,
        individual_count=None,
        locality=inat_obs.get("place_guess") or "",
        municipality="",
        basis_of_record=basis_of_record,
        identification_verification_status=quality_grade,
        verified=(quality_grade == "research"),
        recorded_by=(inat_obs.get("user") or {}).get("login") or "",
        coordinate_uncertainty_in_meters=inat_obs.get("positional_accuracy"),
        references=inat_obs.get("uri") or "",
        data_import=current_data_import,
        source_dataset=inat_dataset,
    )
    obs.set_or_migrate_initial_data_import(current_data_import)
    obs.set_stable_id()
    return obs


class Command(BaseCommand):
    help = (
        "Import observations from iNaturalist for all species with a known inat_taxon_id. "
        "Replaces previous iNaturalist observations only; GBIF observations are unaffected."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_was_successful = False

    def log(self, message: str):
        self.stdout.write(f"{time.ctime()}: {message}")

    def flag_transaction_as_successful(self):
        self.transaction_was_successful = True

    def add_arguments(self, parser):
        parser.add_argument(
            "--updated-since",
            type=str,
            default=None,
            help=(
                "Only fetch observations updated after this ISO 8601 datetime (incremental mode). "
                "Example: 2026-05-01T00:00:00+00:00. "
                "If omitted, a full re-import is performed."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and count observations from iNat but do not write to the database.",
        )

    def _batch_insert(
        self,
        observations: list[Observation],
        current_data_import: DataImport,
    ) -> list[int]:
        """Bulk-insert a list of Observation objects. Returns PKs of genuinely new observations."""
        self.log(f"Bulk inserting {len(observations)} observations...")
        inserted = Observation.objects.bulk_create(
            observations, ignore_conflicts=True
        )

        # Migrate comments from replaced observations (same logic as GBIF import)
        stable_ids = [obs.stable_id for obs in inserted]
        inserted_pks = {obs.pk for obs in inserted if obs.pk}

        existing_by_stable_id = {
            obs.stable_id: obs
            for obs in Observation.objects.filter(stable_id__in=stable_ids).exclude(
                pk__in=inserted_pks
            )
        }

        new_obs_ids = []
        for obs in inserted:
            if obs.pk is None:
                continue
            replaced = existing_by_stable_id.get(obs.stable_id)
            if replaced:
                ObservationComment.objects.filter(observation=replaced).update(
                    observation=obs
                )
            else:
                new_obs_ids.append(obs.pk)

        self.log("Creating unseen observations for new observations")
        create_unseen_observations(Observation.objects.filter(pk__in=new_obs_ids))
        return new_obs_ids

    def handle(self, *args, **options):
        inat_config = settings.GBIF_ALERT.get("INAT_IMPORT_CONFIG", {})

        if not inat_config.get("ENABLED", False):
            self.stdout.write(
                self.style.WARNING(
                    "iNaturalist import is disabled. "
                    "Set GBIF_ALERT['INAT_IMPORT_CONFIG']['ENABLED'] = True to enable."
                )
            )
            return

        place_id: int | None = inat_config.get("PLACE_ID")
        if place_id is None:
            raise CommandError(
                "INAT_IMPORT_CONFIG['PLACE_ID'] is required. "
                "Set it to the iNaturalist place_id for your geographic scope."
            )
        quality_grades: list[str] = inat_config.get("QUALITY_GRADES", ["research"])
        rpm: int = inat_config.get("REQUESTS_PER_MINUTE", 60)
        updated_since: str | None = options.get("updated_since")
        dry_run: bool = options.get("dry_run", False)

        species_qs = Species.objects.filter(inat_taxon_id__isnull=False)
        if not species_qs.exists():
            raise CommandError(
                "No species have an inat_taxon_id. "
                "Run `python manage.py sync_inat_taxon_ids` first."
            )

        self.log(
            f"Starting iNaturalist import: place_id={place_id}, "
            f"quality_grades={quality_grades}, "
            f"{'incremental since ' + updated_since if updated_since else 'full import'}"
        )

        if dry_run:
            self._dry_run(species_qs, place_id, quality_grades, rpm, updated_since)
            return

        start_time = time.time()
        set_maintenance_mode(True)

        try:
            with transaction.atomic():
                transaction.on_commit(self.flag_transaction_as_successful)

                current_data_import = DataImport.objects.create(
                    start=timezone.now(),
                    source=DataImport.SOURCE_INAT,
                )
                self.log(f"Created DataImport #{current_data_import.pk}")

                inat_dataset, _ = Dataset.objects.get_or_create(
                    gbif_dataset_key=INAT_DATASET_KEY,
                    defaults={"name": INAT_DATASET_NAME},
                )
                basis_of_record, _ = BasisOfRecord.objects.get_or_create(
                    name=INAT_BASIS_OF_RECORD
                )

                # Build species lookup: inat_taxon_id → Species
                species_by_inat_id = {
                    s.inat_taxon_id: s for s in species_qs
                }

                total_imported = 0
                total_skipped = 0
                pending: list[Observation] = []
                failed_taxon_ids: set[int] = set()
                successful_taxon_ids: set[int] = set()

                for inat_taxon_id, species in species_by_inat_id.items():
                    self.log(f"Fetching observations for {species.name} (iNat taxon {inat_taxon_id})")

                    try:
                        obs_iter = get_observations(
                            taxon_id=inat_taxon_id,
                            place_id=place_id,
                            quality_grades=quality_grades,
                            requests_per_minute=rpm,
                            updated_since=updated_since,
                        )

                        for raw_obs in obs_iter:
                            obs = build_observation_from_inat(
                                raw_obs,
                                current_data_import,
                                inat_dataset,
                                species,
                                basis_of_record,
                            )
                            if obs is None:
                                total_skipped += 1
                                self.stdout.write("x", ending="")
                                continue

                            pending.append(obs)
                            self.stdout.write(".", ending="")

                            if len(pending) >= BULK_CREATE_CHUNK_SIZE:
                                self._batch_insert(pending, current_data_import)
                                total_imported += len(pending)
                                pending = []

                        successful_taxon_ids.add(inat_taxon_id)

                    except InatApiError as exc:
                        logger.error("iNat API error for taxon %d: %s", inat_taxon_id, exc)
                        self.stdout.write(
                            self.style.WARNING(
                                f"\nSkipped {species.name} due to API error: {exc}"
                            )
                        )
                        failed_taxon_ids.add(inat_taxon_id)

                if pending:
                    self._batch_insert(pending, current_data_import)
                    total_imported += len(pending)

                self.log(f"\nAll observations imported ({total_imported} imported, {total_skipped} skipped)")

                # Migrate unseen state for iNat-sourced observations only.
                # Passing source=SOURCE_INAT ensures GBIF-backed ObservationUnseen entries
                # are never touched by this partial import.
                self.log("Migrating unseen observations (iNat source only)")
                migrate_unseen_observations(
                    current_data_import, source=Observation.SOURCE_INAT
                )

                # Delete previous iNaturalist observations only (GBIF observations untouched).
                # Only delete for taxa that were successfully fetched to avoid data loss on
                # partial API failures (see failed_taxon_ids tracking above).
                if failed_taxon_ids:
                    self.log(
                        f"Skipping delete for {len(failed_taxon_ids)} taxa that had API errors: "
                        f"{failed_taxon_ids}"
                    )
                    safe_to_delete_qs = Observation.objects.filter(
                        source=Observation.SOURCE_INAT,
                        species__inat_taxon_id__in=successful_taxon_ids,
                    ).exclude(data_import=current_data_import)
                else:
                    safe_to_delete_qs = Observation.objects.filter(
                        source=Observation.SOURCE_INAT
                    ).exclude(data_import=current_data_import)

                self.log("Deleting previous iNaturalist observations")
                deleted_count, _ = safe_to_delete_qs.delete()
                self.log(f"Deleted {deleted_count} previous iNaturalist observations")

                self.log("Refreshing materialized views")
                create_or_refresh_materialized_views(
                    zoom_levels=[settings.ZOOM_LEVEL_FOR_MIN_MAX_QUERY]
                )

                # Clean up unused datasets and basis-of-record entries
                # (the iNat dataset itself won't be empty, but clean up any orphans)
                empty_datasets = (
                    Dataset.objects.exclude(gbif_dataset_key=INAT_DATASET_KEY)
                    .annotate(obs_count=Count("observation"))
                    .filter(obs_count=0)
                )
                for dataset in empty_datasets:
                    for alert in dataset.alert_set.all():
                        alert.datasets.remove(dataset)
                    dataset.delete()

                current_data_import.skipped_observations_counter = total_skipped
                current_data_import.complete()
                self.log("Transaction committing")

        finally:
            set_maintenance_mode(False)

        elapsed = time.time() - start_time
        self.log(
            f"iNaturalist import completed in {int(elapsed // 60)}m {int(elapsed % 60)}s"
        )

        if self.transaction_was_successful:
            mail_admins(
                "Successful iNaturalist observations import",
                f"Imported {total_imported} observations from iNaturalist.",
                fail_silently=True,
            )
        else:
            mail_admins(
                "ERROR during iNaturalist observation import",
                "Please check the application logs.",
                fail_silently=True,
            )

    def _dry_run(
        self,
        species_qs,
        place_id: int,
        quality_grades: list[str],
        rpm: int,
        updated_since: str | None,
    ):
        self.log("DRY RUN — no data will be written")
        total = 0
        for species in species_qs:
            count = 0
            try:
                for _ in get_observations(
                    taxon_id=species.inat_taxon_id,
                    place_id=place_id,
                    quality_grades=quality_grades,
                    requests_per_minute=rpm,
                    updated_since=updated_since,
                ):
                    count += 1
            except InatApiError as exc:
                self.stdout.write(self.style.WARNING(f"  {species.name}: API error — {exc}"))
                continue
            self.stdout.write(f"  {species.name}: {count} observations")
            total += count
        self.log(f"DRY RUN complete — {total} observations would be imported")
