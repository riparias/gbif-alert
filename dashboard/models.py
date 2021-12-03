from __future__ import annotations

import hashlib

from typing import Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
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

    CAT_WIDESPREAD = "W"
    CAT_EMERGING = "E"
    CAT_STILL_ABSENT = "SA"

    CAT_CHOICES = [
        (
            CAT_WIDESPREAD,
            _("Widespread and abundant species in the pilot river basins"),
        ),
        (
            CAT_EMERGING,
            _(
                "Emerging species with a very restricted range in the pilot river basins"
            ),
        ),
        (CAT_STILL_ABSENT, _("Species still absent from the pilot river basins")),
    ]

    name = models.CharField(max_length=100)
    gbif_taxon_key = models.IntegerField(unique=True)
    group = models.CharField(max_length=3, choices=GROUP_CHOICES)
    category = models.CharField(max_length=3, choices=CAT_CHOICES)

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
            "categoryCode": self.category,
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
            # We updated the gbif dataset key, so all related occurrences should have a new stable_id
            for occ in self.occurrence_set.all():
                occ.save()

        self.__original_gbif_dataset_key = self.gbif_dataset_key


class DataImport(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    gbif_download_id = models.CharField(max_length=255, blank=True)
    imported_occurrences_counter = models.IntegerField(default=0)

    def set_gbif_download_id(self, download_id: str):
        """Set the download id and immediately save the entry"""
        self.gbif_download_id = download_id
        self.save()

    def complete(self):
        """Method to be called at the end of the import process to finalize this entry"""
        self.end = timezone.now()
        self.completed = True
        self.imported_occurrences_counter = Occurrence.objects.filter(
            data_import=self
        ).count()
        self.save()

    def __str__(self):
        return f"Data import #{self.pk}"


class Occurrence(models.Model):
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

    data_import = models.ForeignKey(DataImport, on_delete=models.PROTECT)
    source_dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("gbif_id", "data_import"), ("stable_id", "data_import")]

    class OtherIdenticalOccurrenceIsNewer(Exception):
        pass

    def save(self, *args, **kwargs):
        self.stable_id = Occurrence.build_stable_id(
            self.occurrence_id, self.source_dataset.gbif_dataset_key
        )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "dashboard:page-occurrence-details", kwargs={"stable_id": self.stable_id}
        )

    def migrate_linked_entities(self):
        """Migrate existing entities (comments, ...) linked to a previous occurrence that share the stable ID

        Does nothing if there's no replaced occurrence
        """
        replaced_occurrence = self.replaced_occurrence
        if replaced_occurrence is not None:
            # 1. Migrating comments
            for comment in replaced_occurrence.occurrencecomment_set.all():
                comment.occurrence = self
                comment.save()

    @property
    def replaced_occurrence(self) -> Optional[Occurrence]:
        """Return the occurrence (from a previous import) that will be replaced by this one

        return None if this occurrence is new to the system
        raises:
        - Occurrence.MultipleObjectsReturned if multiple old occurrences match
        - Occurrence.OtherIdenticalOccurrenceIsNewer if another one has the same stable identifier, but is more recent
        """

        identical_occurrences = self.get_identical_occurrences()
        if identical_occurrences.count() == 0:
            return None
        elif identical_occurrences.count() == 1:
            the_other_one = identical_occurrences[0]
            if the_other_one.data_import.pk < self.data_import.pk:
                return the_other_one
            else:
                raise Occurrence.OtherIdenticalOccurrenceIsNewer

        else:  # Multiple occurrences found, this is abnormal
            raise Occurrence.MultipleObjectsReturned

    def get_identical_occurrences(self) -> QuerySet[Occurrence]:
        """Return 'identical' occurrences (same stable_id), excluding myself)"""
        return Occurrence.objects.exclude(pk=self.pk).filter(stable_id=self.stable_id)

    @property
    def sorted_comments_set(self):
        return self.occurrencecomment_set.order_by("-created_at")

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

        (None, None) in case the occurrence has no location
        """
        if self.location:
            coords = self.location.transform(4326, clone=True).coords
            return coords[0], coords[1]
        return None, None

    @property
    def as_dict(self):  # Keep in sync with JsonOccurrence (TypeScript interface)
        lon, lat = self.lonlat_4326_tuple

        return {
            "id": self.pk,
            "stableId": self.stable_id,
            "gbifId": self.gbif_id,
            "lat": lat,
            "lon": lon,
            "speciesName": self.species.name,
            "datasetName": self.source_dataset.name,
            "date": str(self.date),
        }


class OccurrenceComment(models.Model):
    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Area(models.Model):
    """An area that can be shown to the user, or used to filter occurrences"""

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
