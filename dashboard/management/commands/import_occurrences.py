import tempfile
import datetime
from pathlib import Path
from typing import Dict, Optional

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db.models import QuerySet
from dwca.read import DwCAReader  # type: ignore
from dwca.darwincore.utils import qualname as qn  # type: ignore
from gbif_blocking_occurrences_download import download_occurrences  # type: ignore

from dashboard.models import Species, Occurrence


def build_gbif_predicate(country_code: str, species_list: QuerySet[Species]) -> Dict:
    """Build a GBIF predicate (for occurrence download) targeting a specific country and a list of species"""
    return {
            "predicate": {
                "type": "and",
                "predicates": [
                    {
                        "type": "equals",
                        "key": "COUNTRY",
                        "value": country_code
                    },
                    {
                        "type": "in",
                        "key": "TAXON_KEY",
                        "values": [f"{s.gbif_taxon_key}" for s in species_list]
                    }
                ]
            }
        }


def species_for_row(row):
    """Based first on taxonKey, with fallback to acceptedTaxonKey"""
    taxon_key = int(row.data['http://rs.gbif.org/terms/1.0/taxonKey'])
    try:
        return Species.objects.get(gbif_taxon_key=taxon_key)
    except Species.DoesNotExist:
        accepted_taxon_key = int(row.data['http://rs.gbif.org/terms/1.0/acceptedTaxonKey'])
        return Species.objects.get(gbif_taxon_key=accepted_taxon_key)


class Command(BaseCommand):
    help = 'Download and refresh all occurrence data from GBIF'

    def handle(self, *args, **options) -> None:
        self.stdout.write("Reimporting all occurrences from GBIF")
        predicate = build_gbif_predicate(country_code=settings.RIPARIAS_TARGET_COUNTRYCODE,
                                         species_list=Species.objects.all())

        with tempfile.TemporaryDirectory() as dirname:
            download_dest = Path(dirname, 'download.zip')

            self.stdout.write("Triggering a GBIF download and waiting for it - this can be long...")
            download_occurrences(
                predicate,
                username=settings.RIPARIAS_GBIF_USERNAME,
                password=settings.RIPARIAS_GBIF_PASSWORD,
                output_path=download_dest,
            )

            self.stdout.write("Occurrences downloaded")

            self.stdout.write("Deleting all existing occurrences")
            Occurrence.objects.all().delete()

            self.stdout.write("Importing freshbly downloaded occurrences")
            with DwCAReader(download_dest) as dwca:
                for row in dwca:
                    year_str = row.data[qn('year')]
                    if year_str != '':  # Skip records that don't even have a decent year
                        try:
                            point: Optional[Point] = Point(float(row.data[qn('decimalLongitude')]),
                                                           float(row.data[qn('decimalLatitude')]),
                                                           srid=4326)
                        except ValueError:
                            point = None

                        # Some dates are incomplete(year only - skipping for now)
                        year = int(year_str)
                        try:
                            month = int(row.data[qn('month')])
                            day = int(row.data[qn('day')])
                        except ValueError:
                            month = 1
                            day = 1
                        date = datetime.date(year, month, day)

                        Occurrence.objects.create(
                            gbif_id=int(row.data['http://rs.gbif.org/terms/1.0/gbifID']),
                            species=species_for_row(row),
                            location=point,
                            date=date
                        )

                        self.stdout.write('.', ending='')

        self.stdout.write("Done.")




