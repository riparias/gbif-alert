import datetime
import hashlib
import logging
import os
import resource
import secrets
import smtplib
import time
from typing import Any, Self, cast

import html2text
from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.contrib.gis.db import models
from django.db import connection
from django.contrib.gis.db.models.aggregates import Union as AggregateUnion
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db.models import QuerySet, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.functional import cached_property
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from taggit.managers import TaggableManager

from page_fragments.models import PageFragment, NEWS_PAGE_IDENTIFIER

DATA_SRID = 3857  # Let's keep everything in Google Mercator to avoid reprojections

import gettext

THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))


# Approach from https://stackoverflow.com/questions/37998300/python-gettext-specify-locale-in
def get_translator(lang: str = "en"):
    if lang == "en":
        # Don't try to get a translation if the language is English (would raise an exception)
        return lambda s: s
    else:
        trans = gettext.translation(
            "django",
            localedir=os.path.join(THIS_FILE_DIR, "locale"),
            languages=(lang,),
        )
        return trans.gettext


class User(AbstractUser):
    last_visit_news_page = models.DateTimeField(null=True, blank=True)
    language = models.CharField(
        max_length=10, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE
    )

    # Observation older (observation date) than notification_delay_days will be
    # considered already seen.
    notification_delay_days = models.IntegerField(default=365)

    def obs_match_alerts(self, obs: "Observation") -> bool:
        """Return True if the observation matches at least one of the user's alerts"""
        for alert in self.alert_set.all():
            if alert.observations().filter(pk=obs.pk).exists():
                return True
        return False

    def get_language(self) -> str:
        # Use this method instead of self.language to get the language code (some got en-us as a default value, that will cause issues)
        if self.language == "en-us":
            return "en"
        return self.language

    @property
    def has_alerts_with_unseen_observations(self) -> bool:
        """True if the users has unseen observations in one of their alerts"""
        for alert in self.alert_set.all():
            if alert.has_unseen_observations:
                return True
        return False

    def mark_news_as_visited_now(self) -> None:
        """Mark the news page as visited now"""
        self.last_visit_news_page = timezone.now()
        self.save()

    @property
    def has_unseen_news(self) -> bool:
        """True if the user has unseen news"""
        return (
            self.last_visit_news_page is None
            or self.last_visit_news_page
            < PageFragment.objects.get(identifier=NEWS_PAGE_IDENTIFIER).updated_at
        )

    def empty_all_comments(self) -> None:
        """Empty all comments for this user (to be used prior to deletion)"""
        for comment in self.observationcomment_set.all():
            comment.make_empty()

    class Meta(object):
        unique_together = ("email",)


# Make sure we empty all comments before deleting the user, regardless of the deletion method (bulk, individual,
# admin, ...)
@receiver(pre_delete, sender=User)
def empty_user_comments(sender, instance, **kwargs):
    instance.empty_all_comments()


WebsiteUser = User | AnonymousUser


class Species(models.Model):  # type: ignore
    name = models.CharField(max_length=100)  # Scientific name
    vernacular_name = models.CharField(max_length=100, blank=True)
    gbif_taxon_key = models.IntegerField(unique=True)

    tags = TaggableManager(blank=True)

    class ImageSourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        WIKIPEDIA = "wikipedia", "Wikipedia/Wikimedia"
        GBIF = "gbif", "GBIF occurrence media"

    # Optional single representative picture, referenced by URL (no media files
    # are stored by the app). image_url is a DIRECT IMAGE FILE; image_source_url
    # is the human page to credit/link back to. image_source_type records
    # provenance so the auto-populate command never overwrites manual curation.
    #
    # URLs use max_length=2048 (the conventional max URL length): real Wikimedia
    # thumbnail and GBIF media URLs routinely exceed Django's default of 200.
    image_url = models.URLField(max_length=2048, blank=True)
    image_source_url = models.URLField(max_length=2048, blank=True)
    image_attribution = models.CharField(max_length=500, blank=True)
    image_license = models.CharField(max_length=100, blank=True)
    image_source_type = models.CharField(
        max_length=20, blank=True, choices=ImageSourceType.choices
    )

    class Meta:
        verbose_name_plural = "species"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def display_name_html(self) -> str:
        name = f"<i>{self.name}</i>"
        if self.vernacular_name:
            name = name + f" ({self.vernacular_name})"

        return name

    @property
    def has_image(self) -> bool:
        return bool(self.image_url)

    @property
    def as_dict(self) -> dict[str, Any]:
        # ! keep the return value in sync with the frontend's SpeciesInformation interface
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "scientificName": self.name,
            "vernacularName": self.vernacular_name,
            "gbifTaxonKey": self.gbif_taxon_key,
            "tags": [tag.name for tag in self.tags.all()],
            "imageUrl": self.image_url,
            "imageSourceUrl": self.image_source_url,
            "imageAttribution": self.image_attribution,
            "imageLicense": self.image_license,
            "imageSourceType": self.image_source_type,
        }


class Dataset(models.Model):
    name = models.TextField()
    gbif_dataset_key = models.CharField(max_length=255, unique=True)

    __original_gbif_dataset_key = None

    def __str__(self) -> str:
        return self.name

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__original_gbif_dataset_key = (
            self.gbif_dataset_key
        )  # So we're able to check if it has changed in save()

    class Meta:
        ordering = ["name"]

    @property
    def as_dict(self) -> dict[str, Any]:
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "gbifKey": self.gbif_dataset_key,
            "name": self.name,
        }

    def save(self, *args, **kwargs) -> None:
        # Django 5.1 made save()'s force_insert/force_update keyword-only; just
        # pass everything through (this override only adds post-save logic).
        super().save(*args, **kwargs)

        if self.gbif_dataset_key != self.__original_gbif_dataset_key:
            # We updated the gbif dataset key, so all related observations should have a new stable_id
            for occ in self.observation_set.all():
                occ.save()

        self.__original_gbif_dataset_key = self.gbif_dataset_key


class BasisOfRecord(models.Model):
    name = models.TextField(unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ["name"]

    @property
    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.pk,
            "name": self.name,
        }


class DataImport(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    gbif_download_id = models.CharField(max_length=255, blank=True)
    imported_observations_counter = models.IntegerField(default=0)
    skipped_observations_counter = models.IntegerField(default=0)
    gbif_predicate = models.JSONField(
        blank=True, null=True
    )  # Null if a DwC-A file was provided - no GBIF download

    class Meta:
        ordering = ["-pk"]

    def set_gbif_download_id(self, download_id: str) -> None:
        """Set the download id and immediately save the entry"""
        self.gbif_download_id = download_id
        self.save()

    def complete(self) -> None:
        """Method to be called at the end of the import process to finalize this entry"""
        self.end = timezone.now()
        self.completed = True
        self.imported_observations_counter = Observation.objects.filter(
            data_import=self
        ).count()
        self.save()

    def __str__(self) -> str:
        return (
            f"Data import #{self.pk} ({localize(localtime(self.start), use_l10n=True)})"
        )

    @property
    def as_dict(self) -> dict[str, Any]:
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "name": f"Data import #{self.pk}",
            "startedAt": self.start,
        }


def compute_area_filter_geometry(
    combined_areas, area_filter_mode: str, approaching_distance_km: float
) -> bytes:
    """Pre-compute the target geometry for spatial filtering.

    For 'approaching'/'both' modes, executes one raw SQL query to buffer
    the area in geography space and convert back to SRID 3857.
    Returns the result as EWKB bytes suitable for ST_GeomFromEWKB().

    Parameters
    ----------
    combined_areas : GEOSGeometry
        The union of all selected areas (SRID 3857).
    area_filter_mode : str
        One of 'approaching' or 'both'. Do not call for 'inside' mode -
        use combined_areas.ewkb directly instead.
    approaching_distance_km : float
        Buffer distance in kilometres.
    """
    buffer_m = approaching_distance_km * 1000
    ewkb_param = combined_areas.ewkb

    if area_filter_mode == "approaching":
        sql = (
            "SELECT ST_AsEWKB(ST_Difference("
            "  ST_Transform("
            "    ST_Buffer(ST_Transform(ST_GeomFromEWKB(%s), 4326)::geography, %s)::geometry,"
            "    3857"
            "  ),"
            "  ST_GeomFromEWKB(%s)"
            "))"
        )
        params = [ewkb_param, buffer_m, ewkb_param]
    else:  # "both"
        sql = (
            "SELECT ST_AsEWKB(ST_Transform("
            "  ST_Buffer(ST_Transform(ST_GeomFromEWKB(%s), 4326)::geography, %s)::geometry,"
            "  3857"
            "))"
        )
        params = [ewkb_param, buffer_m]

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return bytes(cursor.fetchone()[0])


def create_unseen_observations(observation_queryset: QuerySet["Observation"]) -> None:
    """
    Create ObservationUnseen entries for all users that have alerts matching the
    provided observations and that are not older than the user's notification delay

    !!! Only applicable to new observations !!!
    """
    # Get the current date
    today = timezone.now().date()

    # Collect all ObservationUnseen objects to create in bulk
    unseen_to_create = []

    # Prefetch alerts with their related species/datasets/basis_of_record/areas to avoid N+1 queries
    users_with_alerts = User.objects.prefetch_related(
        "alert_set__species",
        "alert_set__datasets",
        "alert_set__basis_of_record_filters",
        "alert_set__areas",
    ).all()

    for user in users_with_alerts:
        # Calculate the threshold date based on the user's notification delay
        threshold_date = today - datetime.timedelta(days=user.notification_delay_days)

        # Filter the provided observation queryset to get recent observations
        recent_observations = observation_queryset.filter(date__gt=threshold_date)

        # If no observations are more recent than the user threshold, skip
        if not recent_observations.exists():
            continue

        # Build filter criteria from user's alerts (without executing queries per alert)
        user_alerts = list(user.alert_set.all())  # Already prefetched
        if not user_alerts:
            continue

        # Collect species/dataset/basis_of_record IDs from all alerts (merged).
        # Spatial filtering is handled per-group below because different alerts may
        # use different area_filter_mode / approaching_distance_km values.
        all_species_ids: set[int] = set()
        all_dataset_ids: set[int] = set()
        all_basis_of_record_ids: set[int] = set()
        has_alert_without_dataset_filter = False
        has_alert_without_basis_of_record_filter = False
        has_alert_without_verified_filter = False
        wants_verified = False
        wants_unverified = False

        # Group alerts by (area_filter_mode, approaching_distance_km) so each group
        # can apply its own spatial predicate in one query.
        alerts_by_spatial: dict[tuple, list] = {}

        for alert in user_alerts:
            species_ids = {s.pk for s in alert.species.all()}  # Prefetched
            all_species_ids.update(species_ids)

            dataset_ids = {d.pk for d in alert.datasets.all()}  # Prefetched
            if not dataset_ids:
                has_alert_without_dataset_filter = True
            all_dataset_ids.update(dataset_ids)

            basis_of_record_ids = {
                b.pk for b in alert.basis_of_record_filters.all()
            }  # Prefetched
            if not basis_of_record_ids:
                has_alert_without_basis_of_record_filter = True
            all_basis_of_record_ids.update(basis_of_record_ids)

            if alert.verified_filter == Alert.VERIFIED_FILTER_ALL:
                has_alert_without_verified_filter = True
            elif alert.verified_filter == Alert.VERIFIED_FILTER_VERIFIED_ONLY:
                wants_verified = True
            elif alert.verified_filter == Alert.VERIFIED_FILTER_UNVERIFIED_ONLY:
                wants_unverified = True

            key = (alert.area_filter_mode, alert.approaching_distance_km)
            alerts_by_spatial.setdefault(key, []).append(alert)

        # Build base queryset with non-spatial filters applied once.
        base_obs_qs = recent_observations.filter(species_id__in=all_species_ids)

        if all_dataset_ids and not has_alert_without_dataset_filter:
            base_obs_qs = base_obs_qs.filter(
                source_dataset_id__in=all_dataset_ids
            )

        if all_basis_of_record_ids and not has_alert_without_basis_of_record_filter:
            base_obs_qs = base_obs_qs.filter(
                basis_of_record_id__in=all_basis_of_record_ids
            )

        if not has_alert_without_verified_filter:
            if wants_verified and not wants_unverified:
                base_obs_qs = base_obs_qs.filter(verified=True)
            elif wants_unverified and not wants_verified:
                base_obs_qs = base_obs_qs.filter(verified=False)

        # For each spatial group, apply that group's area filter and collect results.
        # Process AREA_FILTER_INSIDE groups first so they have priority on conflicts.
        def _spatial_sort_key(item: tuple) -> int:
            (mode, _dist), _alerts = item
            return 0 if mode == Alert.AREA_FILTER_INSIDE else 1

        for (mode, distance_km), alerts_group in sorted(
            alerts_by_spatial.items(), key=_spatial_sort_key
        ):
            group_area_ids: set[int] = set()
            has_group_without_area_filter = False
            for alert in alerts_group:
                a_ids = {a.pk for a in alert.areas.all()}  # Prefetched
                if not a_ids:
                    has_group_without_area_filter = True
                group_area_ids.update(a_ids)

            group_obs_qs = base_obs_qs
            if group_area_ids and not has_group_without_area_filter:
                combined_areas = Area.objects.filter(pk__in=group_area_ids).aggregate(
                    area=AggregateUnion("mpoly")
                )["area"]
                if combined_areas:
                    if mode == Alert.AREA_FILTER_INSIDE or not distance_km:
                        group_obs_qs = group_obs_qs.filter(
                            location__within=combined_areas
                        )
                    else:
                        target_ewkb = compute_area_filter_geometry(
                            combined_areas, mode, distance_km
                        )
                        group_obs_qs = group_obs_qs.extra(
                            where=[
                                "ST_Within(dashboard_observation.location, ST_GeomFromEWKB(%s))"
                            ],
                            params=[target_ewkb],
                        )

            # Collect unseen entries for bulk creation
            for obs in group_obs_qs:
                unseen_to_create.append(ObservationUnseen(observation=obs, user=user))

    # Bulk create all unseen observations at once (ignore conflicts for idempotency)
    if unseen_to_create:
        ObservationUnseen.objects.bulk_create(unseen_to_create, ignore_conflicts=True)


class ObservationManager(models.Manager["Observation"]):
    def filtered_from_my_params(
        self,
        species_ids: list[int],
        datasets_ids: list[int],
        basis_of_record_ids: list[int],
        start_date: datetime.date | None,
        end_date: datetime.date | None,
        areas_ids: list[int],
        status_for_user: str | None,
        initial_data_import_ids: list[int],
        user: User | None,  # mandatory if status_for_user is set
        verified_filter: str | None = None,
        area_filter_mode: str = "inside",
        approaching_distance_km: float | None = None,
    ) -> QuerySet["Observation"]:
        # !! IMPORTANT !! Make sure the observation filtering here is equivalent to what's done in
        # views.maps._build_where_clause / _build_joins. Otherwise, observations returned on the map and on other
        # components (table, ...) will be inconsistent.
        # !! If adding new filters, make sure they are documented where the API exposes them: the
        # FiltersQuery schema in dashboard/api_v2_schemas.py (which drives the v2 OpenAPI docs) and
        # the legacy dashboard/views/public_api.py.
        qs = self.model.objects.select_related(
            "species",
            "source_dataset",
            "basis_of_record",
        ).all()

        if species_ids:
            qs = qs.filter(species_id__in=species_ids)
        if datasets_ids:
            qs = qs.filter(source_dataset_id__in=datasets_ids)
        if basis_of_record_ids:
            qs = qs.filter(basis_of_record_id__in=basis_of_record_ids)
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        if areas_ids:
            combined_areas = Area.objects.filter(pk__in=areas_ids).aggregate(
                area=AggregateUnion("mpoly")
            )["area"]
            if area_filter_mode == "inside" or not approaching_distance_km:
                qs = qs.filter(location__within=combined_areas)
            else:
                target_ewkb = compute_area_filter_geometry(
                    combined_areas, area_filter_mode, approaching_distance_km
                )
                qs = qs.extra(
                    where=[
                        "ST_Within(dashboard_observation.location, ST_GeomFromEWKB(%s))"
                    ],
                    params=[target_ewkb],
                )
        if initial_data_import_ids:
            qs = qs.filter(initial_data_import_id__in=initial_data_import_ids)

        if status_for_user and user:
            ous = ObservationUnseen.objects.filter(user=user)
            if status_for_user == "seen":
                qs = qs.exclude(observationunseen__in=ous)
            elif status_for_user == "unseen":
                qs = qs.filter(observationunseen__in=ous)

        if verified_filter == "verified":
            qs = qs.filter(verified=True)
        elif verified_filter == "unverified":
            qs = qs.filter(verified=False)

        return qs


def _log_peak_rss(logger: logging.Logger, label: str) -> None:
    """Log the process peak resident-set size (high-water mark).

    ru_maxrss is the peak RSS since the process started, so it only ever grows;
    logging it after each step shows which step pushed memory usage higher. The
    unit is platform-dependent: kilobytes on Linux, bytes on macOS.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    logger.info(
        f"migrate_unseen_observations: peak RSS after {label}: {peak} "
        "(ru_maxrss; KB on Linux, bytes on macOS)"
    )


# How many rows to pull from the DB per round-trip when streaming with
# .iterator(). Large enough to keep the query count low, small enough that a
# single chunk never dominates memory.
_MIGRATE_CHUNK_SIZE = 10000


def migrate_unseen_observations(current_data_import: "DataImport") -> None:
    """Migrate unseen observations to new observations or delete them if they are no longer relevant."""
    logger = logging.getLogger(__name__)

    logger.info("migrate_unseen_observations: Starting...")
    _log_peak_rss(logger, "start")
    step_start = time.time()

    base_qs = ObservationUnseen.objects.all()

    if not base_qs.exists():
        logger.info(
            "migrate_unseen_observations: No unseen observations, returning early"
        )
        return

    # Step 1: Collect the unique stable_ids of all currently-unseen observations.
    # We fetch only the stable_id column (no model hydration) and stream the rows
    # with .iterator() so that even millions of unseen rows do not all live in
    # memory at once. .distinct() lets the DB collapse duplicates before transfer.
    logger.info("migrate_unseen_observations: Step 1 - Collecting stable_ids...")
    stable_ids = set()
    for stable_id in (
        base_qs.values_list("observation__stable_id", flat=True)
        .distinct()
        .iterator(chunk_size=_MIGRATE_CHUNK_SIZE)
    ):
        stable_ids.add(stable_id)
    logger.info(
        f"migrate_unseen_observations: Collected {len(stable_ids)} unique stable_ids in {time.time() - step_start:.2f}s"
    )
    _log_peak_rss(logger, "step 1 (stable_ids)")

    # Step 2: Find the new observations for these stable_ids in the current import.
    # We keep only the scalar columns the logic needs (id + date), keyed by
    # stable_id - not the full Observation objects (which carry a geometry and
    # several TextFields). Bounded by the number of unique stable_ids.
    step_start = time.time()
    logger.info("migrate_unseen_observations: Step 2 - Querying new observations...")
    new_obs_by_stable_id: dict[str, tuple[int, datetime.date]] = {
        stable_id: (obs_id, obs_date)
        for stable_id, obs_id, obs_date in Observation.objects.filter(
            stable_id__in=stable_ids,
            data_import=current_data_import,
        )
        .values_list("stable_id", "id", "date")
        .iterator(chunk_size=_MIGRATE_CHUNK_SIZE)
    }
    logger.info(
        f"migrate_unseen_observations: Found {len(new_obs_by_stable_id)} matching observations in {time.time() - step_start:.2f}s"
    )
    _log_peak_rss(logger, "step 2 (new observations)")

    # Step 3: Decide, for each unseen row, whether to migrate it to the new
    # observation or delete it. A second streamed pass fetches only the three
    # scalars the decision needs (pk, stable_id, the user's delay) - no joins to
    # hydrate. to_delete holds bare pks; to_update holds lightweight model
    # instances carrying just pk + observation_id for bulk_update.
    step_start = time.time()
    logger.info(
        "migrate_unseen_observations: Step 3 - Processing unseen observations..."
    )
    to_delete: list[int] = []
    to_update: list["ObservationUnseen"] = []
    today = timezone.now().date()

    for i, (pk, stable_id, delay_days) in enumerate(
        base_qs.values_list(
            "pk", "observation__stable_id", "user__notification_delay_days"
        ).iterator(chunk_size=_MIGRATE_CHUNK_SIZE)
    ):
        if i > 0 and i % _MIGRATE_CHUNK_SIZE == 0:
            logger.info(
                f"migrate_unseen_observations: Processed {i} unseen observations..."
            )

        new_obs = new_obs_by_stable_id.get(stable_id)

        if new_obs:
            new_obs_id, new_obs_date = new_obs
            # Check date threshold (cheap check, no DB query)
            threshold_date = today - datetime.timedelta(days=delay_days)
            if new_obs_date < threshold_date:
                # Too old, delete
                to_delete.append(pk)
            else:
                # Still recent enough - update to point to the new observation.
                # Note: We skip obs_match_alerts() check here because:
                # 1. The observation was already in ObservationUnseen, so it matched before
                # 2. obs_match_alerts() is extremely slow (multiple DB queries per call)
                # 3. Even if the observation no longer matches (rare), keeping it as
                #    unseen is a conservative/safe behavior
                to_update.append(ObservationUnseen(pk=pk, observation_id=new_obs_id))
        else:
            # No corresponding observation in new import - delete
            to_delete.append(pk)

    logger.info(
        f"migrate_unseen_observations: Processing done in {time.time() - step_start:.2f}s"
    )
    logger.info(
        f"migrate_unseen_observations: to_update={len(to_update)}, to_delete={len(to_delete)}"
    )
    _log_peak_rss(logger, "step 3 (decisions)")

    # Step 4: Apply changes
    step_start = time.time()
    if to_delete:
        logger.info(
            f"migrate_unseen_observations: Step 4a - Deleting {len(to_delete)} unseen observations..."
        )
        ObservationUnseen.objects.filter(pk__in=to_delete).delete()
        logger.info(
            f"migrate_unseen_observations: Deletion done in {time.time() - step_start:.2f}s"
        )

    step_start = time.time()
    if to_update:
        logger.info(
            f"migrate_unseen_observations: Step 4b - Updating {len(to_update)} unseen observations..."
        )
        ObservationUnseen.objects.bulk_update(
            to_update, ["observation"], batch_size=_MIGRATE_CHUNK_SIZE
        )
        logger.info(
            f"migrate_unseen_observations: Update done in {time.time() - step_start:.2f}s"
        )

    _log_peak_rss(logger, "complete")
    logger.info("migrate_unseen_observations: Complete")


class Observation(models.Model):
    # Pay attention to the fact that this model actually has 4(!) different "identifiers" which serve different
    # purposes. gbif_id, occurrence_id and stable_id are documented below, Django also adds the usual and implicit "pk"
    # field.

    # The GBIF-assigned identifier. We show it to the user (links to GBIF.org, ...) but don't rely on it as a stable
    # identifier anymore. See: https://github.com/riparias/gbif-alert/issues/35#issuecomment-944073702 and
    # https://github.com/gbif/pipelines/issues/604,
    gbif_id = models.CharField(max_length=100)

    # The raw occurrenceId GBIF field, as provided by GBIF data providers retrieved from the data download.
    # It is an important data source, we use it to compute stable_id
    occurrence_id = models.TextField()

    # The computed stable identifier that we can use to identify the same records between data import
    stable_id = models.CharField(max_length=40)

    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    location = models.PointField(blank=True, null=True, srid=DATA_SRID)
    date = models.DateField()
    individual_count = models.IntegerField(blank=True, null=True)
    locality = models.TextField(blank=True)
    municipality = models.TextField(blank=True)
    basis_of_record = models.ForeignKey(BasisOfRecord, on_delete=models.CASCADE)
    identification_verification_status = models.CharField(
        max_length=255, blank=True
    )  # As provided by GBIF, not normalized
    verified = models.BooleanField(default=False)

    recorded_by = models.TextField(blank=True)
    coordinate_uncertainty_in_meters = models.FloatField(blank=True, null=True)
    references = models.TextField(blank=True)

    data_import = models.ForeignKey(DataImport, on_delete=models.PROTECT)
    initial_data_import = models.ForeignKey(
        DataImport,
        on_delete=models.PROTECT,
        related_name="occurrences_initially_imported",
    )
    source_dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)

    objects = ObservationManager()

    class Meta:
        unique_together = [("gbif_id", "data_import"), ("stable_id", "data_import")]
        indexes = [
            models.Index(fields=["stable_id"], name="dashboard_o_stable__idx"),
        ]

    def __str__(self):
        return f"Observation of {self.species} on {self.date} (stable_id: {self.stable_id})"

    class OtherIdenticalObservationIsNewer(Exception):
        pass

    def mark_as_seen_by(self, user: WebsiteUser) -> None:
        """
        Mark the observation as "seen" by a given user.

        Note that this is a high-level function designed to be called directly from a view (for example)
            - Does nothing if the user is anonymous (not signed in)
            - Does nothing if the user has already previously seen this observation
        """

        if user.is_authenticated:
            try:
                self.observationunseen_set.filter(user=user).delete()
            except ObservationUnseen.DoesNotExist:
                pass

    def already_seen_by(self, user: WebsiteUser) -> bool | None:
        """Return True if the observation has already been seen by the user"""
        if user.is_authenticated:
            return not self.observationunseen_set.filter(user=user).exists()
        else:
            return None

    def mark_as_unseen_by(self, user: WebsiteUser) -> bool:
        """Mark the observation as "unseen" for a given user.

        :return: True is successful. Most common causes of failure:
            - the observation doesn't match one of the user's alerts
            - user has not seen this observation yet
            - user is anonymous
        """
        if user.is_authenticated and user.obs_match_alerts(self):
            _, created = ObservationUnseen.objects.get_or_create(
                observation=self, user=user
            )
            if created:
                return True

        return False

    def set_stable_id(self) -> None:
        self.stable_id = Observation.build_stable_id(
            self.occurrence_id, self.source_dataset.gbif_dataset_key
        )

    def save(self, *args, **kwargs) -> None:
        # Beware: the import_observation command uses bulk_create() to create observations, so this save() method is
        # not called. Make sure to keep the logic in sync with import_observation.py
        self.set_stable_id()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse(
            "dashboard:pages:observation-details", kwargs={"stable_id": self.stable_id}
        )

    def set_or_migrate_initial_data_import(
        self, current_data_import: DataImport
    ) -> None:
        """If this is the first import of this observation, set initial_data_import to the current import. Otherwise, migrate its value from the previous observation."""
        replaced_observation = self.replaced_observation
        if replaced_observation is None:
            self.initial_data_import = current_data_import
        else:
            self.initial_data_import = replaced_observation.initial_data_import

    @staticmethod
    def date_older_than_user_delay(user: User, the_date) -> bool:
        today = timezone.now().date()

        return the_date < (
            today - datetime.timedelta(days=user.notification_delay_days)
        )

    @cached_property
    def replaced_observation(self) -> Self | None:
        """Return the observation (from a previous import) that will be replaced by this one

        return None if this observation is new to the system
        raises:
        - Observation.MultipleObjectsReturned if multiple old observations match
        - Observation.OtherIdenticalObservationIsNewer if another one has the same stable identifier, but is more recent


        BEWARE: this method is cached to improve import performances, if you want to call it multiple time on the same
        observation, you may want ti invalidate it first (with del observation.replaced_observation).
        See https://stackoverflow.com/questions/23489548/how-do-i-invalidate-cached-property-in-django
        """

        identical_observations = self.get_identical_observations()
        if identical_observations.count() == 0:
            return None
        elif identical_observations.count() == 1:
            the_other_one = identical_observations[0]
            if the_other_one.data_import.pk < self.data_import.pk:
                return the_other_one
            else:
                raise Observation.OtherIdenticalObservationIsNewer

        else:  # Multiple observations found, this is abnormal
            raise Observation.MultipleObjectsReturned

    def get_identical_observations(self) -> QuerySet[Self]:
        """Return 'identical' observations (same stable_id), excluding myself"""
        return Observation.objects.exclude(pk=self.pk).filter(  # type: ignore
            stable_id=Observation.build_stable_id(
                self.occurrence_id, self.source_dataset.gbif_dataset_key
            )
        )

    @property
    def sorted_comments_set(self) -> QuerySet["ObservationComment"]:
        return self.observationcomment_set.order_by("-created_at")

    @staticmethod
    def build_stable_id(occurrence_id: str, dataset_key: str) -> str:
        """Compute a unique/portable/repeatable hash depending on occurrence_id and dataset_key

        Return value is a 40-char string containing only hexadecimal characters
        """
        s = f"occ_id: {occurrence_id} d_id: {dataset_key}"
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    @property
    def lat(self) -> float | None:
        return self.lonlat_4326_tuple[1]

    @property
    def lon(self) -> float | None:
        return self.lonlat_4326_tuple[0]

    @property
    def lonlat_4326_tuple(self) -> tuple[float | None, float | None]:
        """Coordinates as a (lon, lat) tuple, in EPSG:4326

        (None, None) in case the observation has no location
        """
        if self.location:
            coords = self.location.transform(4326, clone=True).coords  # type: ignore
            return coords[0], coords[1]
        return None, None

    # Keep in sync with JsonObservation (TypeScript interface)
    def as_dict(self, for_user: WebsiteUser) -> dict[str, Any]:
        """Returns the model representation has a dict.

        If the user is not anonymous, it also contains status data (seen / unseen)"""
        lon, lat = self.lonlat_4326_tuple

        d = {
            "id": self.pk,
            "stableId": self.stable_id,
            "gbifId": self.gbif_id,
            "lat": lat,
            "lon": lon,
            "scientificName": self.species.name,
            "vernacularName": self.species.vernacular_name,
            "displayNameHtml": self.species.display_name_html(),
            "datasetName": self.source_dataset.name,
            "date": str(self.date),
        }

        if for_user.is_authenticated:
            try:
                self.observationunseen_set.get(user=for_user)
                d["seenByCurrentUser"] = False
            except ObservationUnseen.DoesNotExist:
                d["seenByCurrentUser"] = True

        return d

    def as_short_dict(self) -> dict[str, Any]:
        """Returns a short representation of the model as a dict"""
        lon, lat = self.lonlat_4326_tuple

        return {
            "id": self.pk,
            "lat": lat,
            "lon": lon,
            "scientificName": self.species.name,
            "speciesId": self.species.pk,
            "date": str(self.date),
        }


class ObservationComment(models.Model):
    """ " A comment on an observation, left by an authenticated visitor"""

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # If an author deletes their account, we keep track of the comment's existence
    # (so a conversation under an observation doesn't seem too absurd) but delete its content. Such records can be
    # detected with the 'emptied_because_author_deleted_account' flag
    emptied_because_author_deleted_account = models.BooleanField(default=False)

    def make_empty(self):
        """
        Make the comment empty, and mark it as such.

        This is the method to be called before deleting a user account.
        """
        self.text = ""
        self.author = None
        self.emptied_because_author_deleted_account = True
        self.save()


class MyAreaManager(models.Manager["Area"]):
    def owned_by(self, user: WebsiteUser) -> QuerySet["Area"]:
        # owned_by is only meaningful for an authenticated user; the FK lookup
        # rejects AnonymousUser, so narrow the WebsiteUser union to User.
        return (
            super(MyAreaManager, self)
            .get_queryset()
            .filter(owner=cast("User", user))
        )

    def public(self) -> QuerySet["Area"]:
        return super(MyAreaManager, self).get_queryset().filter(owner=None)

    def available_to(self, user: WebsiteUser) -> QuerySet["Area"]:
        if user.is_authenticated:
            return (
                super(MyAreaManager, self)
                .get_queryset()
                .filter(Q(owner=user) | Q(owner=None))
            )
        else:
            return self.public()


class Area(models.Model):
    """An area that can be shown to the user, or used to filter observations"""

    mpoly = models.MultiPolygonField(srid=DATA_SRID)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True
    )  # an area can be public or user-specific
    name = models.CharField(max_length=255)

    tags = TaggableManager(blank=True)
    objects = MyAreaManager()

    class Meta:
        ordering = ["name"]

    class HasAlerts(Exception):
        """This area is referenced by at least one alert"""

    def delete(self, *args, **kwargs):
        if self.alert_set.count() > 0:
            raise Area.HasAlerts
        super(Area, self).delete(*args, **kwargs)

    @property
    def is_public(self) -> bool:
        return self.owner is None

    @property
    def is_user_specific(self) -> bool:
        return not self.is_public

    def is_owned_by(self, user: WebsiteUser) -> bool:
        return self.is_user_specific and self.owner == user

    def is_available_to(self, user: WebsiteUser) -> bool:
        return self.is_public or self.is_owned_by(user)

    def __str__(self) -> str:
        return self.name

    def to_dict(self, include_geojson: bool):
        d = {
            "id": self.pk,
            "name": self.name,
            "isUserSpecific": self.is_user_specific,
            "tags": [tag.name for tag in self.tags.all()],
        }

        if include_geojson:
            d["geojson_str"] = self.mpoly.geojson

        return d


class ObservationView(models.Model):
    """
    !! This model is deprecated, we now use ObservationUnseen instead !!
    (ObservationUnseen is a reversed logic: we store unseen observations instead of seen ones)
    This one shouldn't be used in the codebase anymore, however we do keep it for the
    sake of older data migrations !!

    This models keeps a history of when a user has first seen details about an observation

    - If no entry for the user/observation pair: the user has never seen details about this observation
    - Else: the timestamp of the *first* visit is kept (no sophisticated history mechanism)
    """

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ("observation", "user"),
        ]


class ObservationUnseen(models.Model):
    """
    To replace the ObservationView model, but with reversed logic: we store unseen
    observations instead of seen ones

    Hopefully this will solve some scaling issues will have, since we have options to
    keep the number of unseen observations relatively low
    """

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def relevant_for_user(self, date_new_observation) -> bool:
        """Return True if this "unseen object" is still relevant for the user"""
        # TODO: test this
        if self.observation.date_older_than_user_delay(
            self.user, the_date=date_new_observation
        ):
            return False
        else:
            return self.user.obs_match_alerts(self.observation)

    class Meta:
        unique_together = [
            ("observation", "user"),
        ]


class Alert(models.Model):
    """The per-user configured alerts

    An alert is user specific.
    Datasets is an optional filter. If left blank, all source datasets will be taken into account.
    Area is an optional filter. If left blank, data is not filtered by location (which might be more than the selection of all areas)
    We choose to not extend this logic to species. By keeping this list explicit, we allow site administrators
    to add new species and areas without having to worry about silently editing user alerts.
    """

    NO_EMAILS = "N"
    DAILY_EMAILS = "D"
    WEEKLY_EMAILS = "W"
    MONTHLY_EMAILS = "M"

    VERIFIED_FILTER_ALL = "all"
    VERIFIED_FILTER_VERIFIED_ONLY = "verified"
    VERIFIED_FILTER_UNVERIFIED_ONLY = "unverified"

    VERIFIED_FILTER_CHOICES = [
        (VERIFIED_FILTER_ALL, "All observations"),
        (VERIFIED_FILTER_VERIFIED_ONLY, "Verified only"),
        (VERIFIED_FILTER_UNVERIFIED_ONLY, "Unverified only"),
    ]

    AREA_FILTER_INSIDE = "inside"
    AREA_FILTER_APPROACHING = "approaching"
    AREA_FILTER_BOTH = "both"

    AREA_FILTER_MODE_CHOICES = [
        (AREA_FILTER_INSIDE, "Inside the area"),
        (AREA_FILTER_APPROACHING, "Close to the area (not inside)"),
        (AREA_FILTER_BOTH, "Inside or close to the area"),
    ]

    EMAIL_NOTIFICATION_CHOICES = [
        (NO_EMAILS, _("No emails")),
        (DAILY_EMAILS, _("Daily")),
        (WEEKLY_EMAILS, _("Weekly")),
        (MONTHLY_EMAILS, _("Monthly")),
    ]

    EMAIL_NOTIFICATION_DELTAS = (
        {  # After how much time should we be ready to send a new email
            DAILY_EMAILS: datetime.timedelta(hours=22),
            WEEKLY_EMAILS: datetime.timedelta(days=6, hours=22),
            MONTHLY_EMAILS: datetime.timedelta(weeks=4),
        }
    )

    name = models.CharField(verbose_name=_("name"), max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    species = models.ManyToManyField(
        Species,
        verbose_name=_("species"),
        blank=False,
        help_text=_(
            "To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )
    datasets = models.ManyToManyField(  # type: ignore[var-annotated]  # django-stubs 5.2 can't infer the M2M descriptor
        Dataset,
        verbose_name=_("datasets"),
        blank=True,
        help_text=_(
            "Optional (no selection = notify me for all datasets). To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )
    basis_of_record_filters = models.ManyToManyField(  # type: ignore[var-annotated]  # django-stubs 5.2 can't infer the M2M descriptor
        BasisOfRecord,
        verbose_name=_("basis of record"),
        blank=True,
        help_text=_(
            "Optional (no selection = notify me for all basis of records). To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )
    areas = models.ManyToManyField(  # type: ignore[var-annotated]  # django-stubs 5.2 can't infer the M2M descriptor
        Area,
        blank=True,
        verbose_name=_("areas"),
        help_text=_(
            "Optional (no selection = notify me for all data in the system). To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )

    area_filter_mode = models.CharField(
        max_length=20,
        choices=AREA_FILTER_MODE_CHOICES,
        default=AREA_FILTER_INSIDE,
    )

    approaching_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Required when area_filter_mode is 'approaching' or 'both'. Distance in km (max 50).",
    )

    email_notifications_frequency = models.CharField(
        max_length=3,
        choices=EMAIL_NOTIFICATION_CHOICES,
        default=WEEKLY_EMAILS,
        verbose_name=_("email notifications frequency"),
    )

    verified_filter = models.CharField(
        max_length=10,
        choices=VERIFIED_FILTER_CHOICES,
        default=VERIFIED_FILTER_ALL,
    )

    last_email_sent_on = models.DateTimeField(blank=True, null=True, default=None)

    class Meta:
        unique_together = [("user", "name")]

    def clean(self) -> None:
        if self.area_filter_mode in (self.AREA_FILTER_APPROACHING, self.AREA_FILTER_BOTH):
            if self.approaching_distance_km is None:
                raise ValidationError(
                    {"approaching_distance_km": "This field is required when the area filter mode is not 'inside'."}
                )
            if self.approaching_distance_km <= 0:
                raise ValidationError(
                    {"approaching_distance_km": "The distance must be greater than 0."}
                )
            if self.approaching_distance_km > 50:
                raise ValidationError(
                    {"approaching_distance_km": "The distance must be 50 km or less."}
                )
        elif self.area_filter_mode == self.AREA_FILTER_INSIDE:
            if self.approaching_distance_km is not None:
                raise ValidationError(
                    {"approaching_distance_km": "This field must be empty when the area filter mode is 'inside'."}
                )

    def get_absolute_url(self) -> str:
        return reverse("dashboard:pages:alert-details", kwargs={"alert_id": self.id})

    @property
    def areas_list(self) -> str:
        return ", ".join(self.areas.order_by("name").values_list("name", flat=True))

    @property
    def area_description(self) -> str:
        """Human-readable description of the area filter for use in emails and the alert detail page.

        Returns an empty string when no areas are configured (caller should fall back to "all").
        """
        area_names = list(self.areas.order_by("name").values_list("name", flat=True))
        if not area_names:
            return ""
        quoted_names = [f"'{n}'" for n in area_names]
        if len(quoted_names) == 1:
            quoted = quoted_names[0]
        else:
            quoted = ", ".join(quoted_names[:-1]) + " or " + quoted_names[-1]
        if self.area_filter_mode == self.AREA_FILTER_INSIDE:
            return f"inside {quoted}"
        dist = f"{self.approaching_distance_km:g}"
        if self.area_filter_mode == self.AREA_FILTER_APPROACHING:
            return f"within {dist} km of {quoted}"
        # AREA_FILTER_BOTH
        return f"inside or within {dist} km of {quoted}"

    @property
    def datasets_list(self) -> str:
        return ", ".join(self.datasets.order_by("name").values_list("name", flat=True))

    @property
    def basis_of_record_list(self) -> str:
        return ", ".join(
            self.basis_of_record_filters.order_by("name").values_list("name", flat=True)
        )

    @property
    def verified_filter_display(self) -> str:
        return dict(self.VERIFIED_FILTER_CHOICES).get(self.verified_filter, self.verified_filter)

    @property
    def species_list(self) -> str:
        return ", ".join(self.species.order_by("name").values_list("name", flat=True))

    @property
    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.pk,
            "name": self.name,
            "speciesIds": [s.pk for s in self.species.all()],
            "datasetIds": [d.pk for d in self.datasets.all()],
            "basisOfRecordIds": [b.pk for b in self.basis_of_record_filters.all()],
            "areaIds": [a.pk for a in self.areas.all()],
            "emailNotificationsFrequency": self.email_notifications_frequency,
            "verifiedFilter": self.verified_filter,
            "areaFilterMode": self.area_filter_mode,
            "approachingDistanceKm": self.approaching_distance_km,
        }

    def observations(self) -> QuerySet[Observation]:
        """Return all observations matching this alert"""
        # TODO: test this
        return Observation.objects.filtered_from_my_params(
            species_ids=[s.pk for s in self.species.all()],
            datasets_ids=[d.pk for d in self.datasets.all()],
            basis_of_record_ids=[b.pk for b in self.basis_of_record_filters.all()],
            areas_ids=[a.pk for a in self.areas.all()],
            start_date=None,
            end_date=None,
            initial_data_import_ids=[],
            status_for_user=None,
            user=self.user,
            verified_filter=self.verified_filter,
            area_filter_mode=self.area_filter_mode,
            approaching_distance_km=self.approaching_distance_km,
        )

    def unseen_observations(self) -> QuerySet[Observation]:
        """Return all unseen observations matching this alert"""
        return Observation.objects.filtered_from_my_params(
            species_ids=[s.pk for s in self.species.all()],
            datasets_ids=[d.pk for d in self.datasets.all()],
            basis_of_record_ids=[b.pk for b in self.basis_of_record_filters.all()],
            areas_ids=[a.pk for a in self.areas.all()],
            start_date=None,
            end_date=None,
            initial_data_import_ids=[],
            status_for_user="unseen",
            user=self.user,
            verified_filter=self.verified_filter,
            area_filter_mode=self.area_filter_mode,
            approaching_distance_km=self.approaching_distance_km,
        )

    def unseen_observations_sample(self, sample_size=10) -> QuerySet[Observation]:
        """For notification emails: show max sample_size observations, most recent first"""
        obs = self.unseen_observations().order_by("-date")
        if obs.count() > sample_size:
            obs = obs[:sample_size]

        return obs

    @property
    def unseen_observations_count(self) -> int:
        """The number of unseen observations for this alert"""
        return self.unseen_observations().count()

    @property
    def has_unseen_observations(self) -> bool:
        """True if this alert has unseen observations"""
        return self.unseen_observations_count > 0

    def email_should_be_sent_now(self) -> bool:
        """Returns true if a notification email for this alert should be sent at the present time.

        Use some margins so emails are sent at a decent frequency if this is called daily.
        """
        if (
            self.email_notifications_frequency != self.NO_EMAILS
            and self.unseen_observations_count > 0
        ):
            if (
                self.last_email_sent_on is None
            ):  # the user wants e-mails, has unseen observations and has not received yet...
                return True  # ...so, now is  a good time
            else:
                # the user wants e-mails, has unseen observations but as already received notifications.
                # Is it now a good time for a new one?
                delta = self.EMAIL_NOTIFICATION_DELTAS[
                    self.email_notifications_frequency
                ]
                if self.last_email_sent_on + delta < timezone.now():
                    return True
        return False

    def send_notification_email(self) -> bool:
        """Send the notification e-mail

        No checks are done, it's the responsibility of the caller to use email_should_be_sent_now() before calling this
        method.
        """
        language_code = self.user.get_language()

        # Message subject
        _ = get_translator(language_code)
        unseen_obs_translated = _("new observation(s) for your alert")
        subject = f"{settings.EMAIL_SUBJECT_PREFIX} {self.unseen_observations().count()} {unseen_obs_translated} {self.name}"

        # Message body
        msg_html = render_to_string(
            f"dashboard/emails/alert_notification.{language_code}.html",
            {
                "alert": self,
                "site_base_url": settings.SITE_BASE_URL,
                "site_name": settings.GBIF_ALERT["SITE_NAME"],
            },
        )

        msg_plain = html2text.html2text(msg_html)

        try:
            send_mail(
                subject,
                msg_plain,
                settings.SERVER_EMAIL,
                [self.user.email],
                html_message=msg_html,
            )
        except smtplib.SMTPException:
            logging.exception("Error sending notification emails")
            return False

        self.last_email_sent_on = timezone.now()
        self.save(update_fields=["last_email_sent_on"])
        return True


class ApiToken(models.Model):
    """A personal access token that authenticates API requests as its owner.

    Only a hash of the token is stored; the raw value is returned once at
    creation and is never recoverable afterwards. A token grants the same
    access as its owning user (it is not scoped).

    Attributes
    ----------
    user : User
        The owner; the token authenticates as this user.
    name : str
        A user-provided label to tell tokens apart.
    token_hash : str
        SHA-256 hex digest of the raw token; the lookup key.
    prefix : str
        The first characters of the raw token, kept for display only.
    created_at : datetime.datetime
    last_used_at : datetime.datetime or None
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens"
    )
    name = models.CharField(max_length=100, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    prefix = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.prefix}... ({self.user})"

    @staticmethod
    def hash_token(raw: str) -> str:
        """Return the SHA-256 hex digest used as the stored lookup key."""
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def create_for(cls, user: "User", name: str = "") -> tuple["ApiToken", str]:
        """Create a token for `user` and return (instance, raw_token).

        The raw token is only available here; afterwards only its hash is stored.
        """
        raw = secrets.token_urlsafe(32)
        token = cls.objects.create(
            user=user, name=name, token_hash=cls.hash_token(raw), prefix=raw[:8]
        )
        return token, raw
