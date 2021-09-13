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


class Occurrence(models.Model):
    gbif_id = models.CharField(max_length=100, unique=True)
    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    location = models.PointField(blank=True, null=True, srid=3857)
    date = models.DateField()

    @property
    def as_dict(self):
        lon, lat = self.location.transform(4326, clone=True).coords

        return {
            "id": self.pk,
            "gbifId": self.gbif_id,
            "lat": str(lat)[:6],
            "lon": str(lon)[:6],
            "speciesName": self.species.name,
            "date": str(self.date),
        }
