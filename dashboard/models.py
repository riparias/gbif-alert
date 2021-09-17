from django.contrib.gis.db import models
from django.utils.translation import ugettext_lazy as _


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


class DataImport(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    gbif_download_id = models.CharField(max_length=255, blank=True)
    imported_occurrences_counter = models.IntegerField(default=0)

    def __str__(self):
        return f"Data import #{self.pk}"


class Occurrence(models.Model):
    gbif_id = models.CharField(max_length=100)
    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    location = models.PointField(blank=True, null=True, srid=3857)
    date = models.DateField()

    data_import = models.ForeignKey(DataImport, on_delete=models.PROTECT)

    class Meta:
        unique_together = ["gbif_id", "data_import"]

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
            "gbifId": self.gbif_id,
            "lat": lat,
            "lon": lon,
            "speciesName": self.species.name,
            "date": str(self.date),
        }
