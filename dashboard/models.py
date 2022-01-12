from __future__ import annotations

import datetime
import hashlib

from typing import Optional, Union

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.contrib.gis.db import models
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

DATA_SRID = 3857  # Let's keep everything in Google Mercator to avoid reprojections


class User(AbstractUser):
    pass


class Species(models.Model):
    GROUP_PLANT = "PL"
    GROUP_CRAYFISH = "CR"

    GROUP_CHOICES = [(GROUP_PLANT, _("Plants")), (GROUP_CRAYFISH, _("Crayfishes"))]

    name = models.CharField(max_length=100)
    gbif_taxon_key = models.IntegerField(unique=True)
    group = models.CharField(max_length=3, choices=GROUP_CHOICES)

    class Meta:
        verbose_name_plural = "species"

    def __str__(self):
        return self.name

    @property
    def as_dict(self):
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "scientificName": self.name,
            "gbifTaxonKey": self.gbif_taxon_key,
            "groupCode": self.group,
        }


class Dataset(models.Model):
    name = models.CharField(max_length=255)
    gbif_dataset_key = models.CharField(max_length=255, unique=True)

    __original_gbif_dataset_key = None

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_gbif_dataset_key = (
            self.gbif_dataset_key
        )  # So we're able to check if it has changed in save()

    @property
    def as_dict(self):
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "gbifKey": self.gbif_dataset_key,
            "name": self.name,
        }

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        super().save(force_insert, force_update, *args, **kwargs)

        if self.gbif_dataset_key != self.__original_gbif_dataset_key:
            # We updated the gbif dataset key, so all related observations should have a new stable_id
            for occ in self.observation_set.all():
                occ.save()

        self.__original_gbif_dataset_key = self.gbif_dataset_key


class DataImport(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    gbif_download_id = models.CharField(max_length=255, blank=True)
    imported_observations_counter = models.IntegerField(default=0)

    def set_gbif_download_id(self, download_id: str):
        """Set the download id and immediately save the entry"""
        self.gbif_download_id = download_id
        self.save()

    def complete(self):
        """Method to be called at the end of the import process to finalize this entry"""
        self.end = timezone.now()
        self.completed = True
        self.imported_observations_counter = Observation.objects.filter(
            data_import=self
        ).count()
        self.save()

    def __str__(self):
        return f"Data import #{self.pk}"


class Observation(models.Model):
    # Pay attention to the fact that this model actually has 4(!) different "identifiers" which serve different
    # purposes. gbif_id, occurrence_id and stable_id are documented below, Django also adds the usual and implicit "pk"
    # field.

    # The GBIF-assigned identifier. We show it to the user (links to GBIF.org, ...) but don't rely on it as a stable
    # identifier anymore. See: https://github.com/riparias/early-warning-webapp/issues/35#issuecomment-944073702 and
    # https://github.com/gbif/pipelines/issues/604,
    gbif_id = models.CharField(max_length=100)

    # The raw occurrenceId GBIF field, as provided by GBIF data providers retrieved from the data download.
    # It is an important data source, we use it to compute stable_id
    occurrence_id = models.TextField()

    # The computed stable identifier that we can use to identify the same records between data import
    stable_id = models.CharField(max_length=40)

    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    location = models.PointField(blank=True, null=True, srid=DATA_SRID)
    date = models.DateField()
    individual_count = models.IntegerField(blank=True, null=True)
    locality = models.TextField(blank=True)
    municipality = models.TextField(blank=True)
    basis_of_record = models.TextField(blank=True)
    recorded_by = models.TextField(blank=True)
    coordinate_uncertainty_in_meters = models.FloatField(blank=True, null=True)

    data_import = models.ForeignKey(DataImport, on_delete=models.PROTECT)
    source_dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("gbif_id", "data_import"), ("stable_id", "data_import")]

    class OtherIdenticalObservationIsNewer(Exception):
        pass

    def get_admin_url(self):
        return reverse(
            "admin:%s_%s_change" % (self._meta.app_label, self._meta.model_name),
            args=(self.id,),
        )

    def mark_as_viewed_by(self, user: Union[User, AnonymousUser]) -> None:
        """
        Mark the observation as "viewed" by a given user.

        Note that this is a high-level function designed to be called directly from a view (for example)
            - Does nothing if the user is anonymous (not signed in)
            - Does nothing if the user has already previously viewed this observation
        """

        if user.is_authenticated:
            try:
                self.observationview_set.get(user=user)
            except ObservationView.DoesNotExist:
                ObservationView.objects.create(observation=self, user=user)

    def first_viewed_at(
        self, user: Union[User, AnonymousUser]
    ) -> Optional[datetime.datetime]:
        """Return the time a user as first viewed this observation

        Returns none if the user is not logged in, or if they have not viewed the observation yet
        """

        # We want to check if user is not anonymous, but apparently is_authenticated is the preferred method
        if user.is_authenticated:
            try:
                return self.observationview_set.get(user=user).timestamp
            except ObservationView.DoesNotExist:
                return None
        return None

    def mark_as_not_viewed_by(self, user: Union[User, AnonymousUser]) -> bool:
        """Return True is successful, False otherwise (probable causes: user has not viewed this observation yet / user is anonymous)"""
        if user.is_authenticated:
            try:
                self.observationview_set.get(user=user).delete()
                return True
            except ObservationView.DoesNotExist:
                return False

        return False

    def save(self, *args, **kwargs):
        self.stable_id = Observation.build_stable_id(
            self.occurrence_id, self.source_dataset.gbif_dataset_key
        )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "dashboard:page-observation-details", kwargs={"stable_id": self.stable_id}
        )

    def migrate_linked_entities(self):
        """Migrate existing entities (comments, ...) linked to a previous observation that share the stable ID

        Does nothing if there's no replaced observation
        """
        replaced_observation = self.replaced_observation
        if replaced_observation is not None:
            # 1. Migrating comments
            for comment in replaced_observation.observationcomment_set.all():
                comment.observation = self
                comment.save()
            # 2. Migrating user views
            for observation_view in replaced_observation.observationview_set.all():
                observation_view.observation = self
                observation_view.save()

    @property
    def replaced_observation(self) -> Optional[Observation]:
        """Return the observation (from a previous import) that will be replaced by this one

        return None if this observation is new to the system
        raises:
        - Observation.MultipleObjectsReturned if multiple old observations match
        - Observation.OtherIdenticalObservationIsNewer if another one has the same stable identifier, but is more recent
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

    def get_identical_observations(self) -> QuerySet[Observation]:
        """Return 'identical' observations (same stable_id), excluding myself)"""
        return Observation.objects.exclude(pk=self.pk).filter(stable_id=self.stable_id)

    @property
    def sorted_comments_set(self):
        return self.observationcomment_set.order_by("-created_at")

    @staticmethod
    def build_stable_id(occurrence_id: str, dataset_key: str) -> str:
        """Compute a unique/portable/repeatable hash depending on occurrence_id and dataset_key

        Return value is a 40-char string containing only hexadecimal characters
        """
        s = f"occ_id: {occurrence_id} d_id: {dataset_key}"
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    @property
    def lat(self):
        return self.lonlat_4326_tuple[1]

    @property
    def lon(self):
        return self.lonlat_4326_tuple[0]

    @property
    def lonlat_4326_tuple(self):
        """Coordinates as a (lon, lat) tuple, in EPSG:4326

        (None, None) in case the observation has no location
        """
        if self.location:
            coords = self.location.transform(4326, clone=True).coords
            return coords[0], coords[1]
        return None, None

    def as_dict(
        self, for_user
    ):  # Keep in sync with JsonObservation (TypeScript interface)
        lon, lat = self.lonlat_4326_tuple

        d = {
            "id": self.pk,
            "stableId": self.stable_id,
            "gbifId": self.gbif_id,
            "lat": lat,
            "lon": lon,
            "speciesName": self.species.name,
            "datasetName": self.source_dataset.name,
            "date": str(self.date),
        }

        if for_user.is_authenticated:
            try:
                self.observationview_set.get(user=for_user)
                d["viewedByCurrentUser"] = True
            except ObservationView.DoesNotExist:
                d["viewedByCurrentUser"] = False

        return d


class ObservationComment(models.Model):
    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Area(models.Model):
    """An area that can be shown to the user, or used to filter observations"""

    mpoly = models.MultiPolygonField(srid=DATA_SRID)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True
    )  # an area can be global or user-specific
    name = models.CharField(max_length=255)

    @property
    def is_global(self) -> bool:
        return self.owner is None

    @property
    def is_user_specific(self) -> bool:
        return not self.is_global

    def is_owned_by(self, user) -> bool:
        return self.is_user_specific and self.owner == user

    def is_available_to(self, user) -> bool:
        return self.is_global or self.is_owned_by(user)

    def __str__(self) -> str:
        return self.name

    def to_dict(self, include_geojson: bool):
        d = {
            "id": self.pk,
            "name": self.name,
            "isUserSpecific": self.is_user_specific,
        }

        if include_geojson:
            d["geojson_str"] = self.mpoly.geojson

        return d


class ObservationView(models.Model):
    """
    This models keeps an history of when a user has first seen details about an observation

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


class Alert(models.Model):
    """The per-user configured alerts"""

    NO_EMAILS = "N"
    DAILY_EMAILS = "D"
    WEEKLY_EMAILS = "W"
    MONTHLY_EMAILS = "M"

    EMAIL_NOTIFICATION_CHOICES = [
        (NO_EMAILS, "No emails"),
        (DAILY_EMAILS, "Daily"),
        (WEEKLY_EMAILS, "Weekly"),
        (MONTHLY_EMAILS, "Monthly"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    species = models.ManyToManyField(Species)
    datasets = models.ManyToManyField(Dataset)
    areas = models.ManyToManyField(Area)

    email_notifications_frequency = models.CharField(
        max_length=3, choices=EMAIL_NOTIFICATION_CHOICES, default=WEEKLY_EMAILS
    )

    @property
    def areas_list(self) -> str:
        return ", ".join(self.areas.order_by("name").values_list("name", flat=True))

    @property
    def datasets_list(self) -> str:
        return ", ".join(self.datasets.order_by("name").values_list("name", flat=True))

    @property
    def species_list(self) -> str:
        return ", ".join(self.species.order_by("name").values_list("name", flat=True))
