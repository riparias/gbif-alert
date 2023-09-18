"""Custom script to import the N2000 areas for the LIFE RIPARIAS project.

The usual load_area.py script cannot be used because the specifities of the data make it unsuitable for the usual
LayerMapping helper.
"""
import os

from django.contrib.gis.gdal import DataSource
from django.core.management import BaseCommand

from dashboard.models import Area, DATA_SRID

THIS_FILE_DIR = os.path.dirname(__file__)
SOURCE_DATA_GPKG_PATH = (
    f"{THIS_FILE_DIR}/../../../source_data/public_areas/natura2000/natura2000_BE.gpkg"
)


class Command(BaseCommand):
    help = "Import N2000 areas in the database. "

    def handle(self, *args, **options) -> None:
        self.stdout.write("Importing N2000 areas")
        self.stdout.write("Opening source file")
        ds = DataSource(SOURCE_DATA_GPKG_PATH)
        layer = ds[0]
        self.stdout.write(f"Found {layer.num_feat} features")  # type: ignore
        for feature in layer:
            area_name = f"{feature['SITECODE']} - {feature['SITENAME']}"
            tags = ["Natura2000"]

            # tags.append(f"sitetype {feature['SITETYPE']}")
            site_type = feature["SITETYPE"].value
            if site_type == "B":
                tags.append("habitat directive")
            elif site_type == "A":
                tags.append("bird directive")
            elif site_type == "C":
                tags.append("habitat directive")
                tags.append("bird directive")

            if feature["Brussels"].value == 1:
                tags.append("Brussels")
            if feature["Wallonia"].value == 1:
                tags.append("Wallonia")
            if feature["Flanders"].value == 1:
                tags.append("Flanders")

            self.stdout.write(f"Creating area {area_name}, with tags {tags}")
            reprojected_geom = feature.geom.transform(DATA_SRID, clone=True)
            area = Area.objects.create(mpoly=reprojected_geom.wkt, name=area_name)  # type: ignore
            area.tags.add(*tags)
