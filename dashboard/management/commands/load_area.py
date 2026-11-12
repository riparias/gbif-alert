from django.contrib.gis.gdal import DataSource
from django.contrib.gis.utils.layermapping import LayerMapping
from django.core.management.base import BaseCommand, CommandParser

from dashboard.models import Area


class Command(BaseCommand):
    help = (
        "Import public areas from a vector file (shapefile, GeoJSON, GeoPackage, ...). "
        "Each feature of the first layer becomes one area, named after the --name-field attribute."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path", help="Path to the source file")
        parser.add_argument(
            "--name-field",
            required=True,
            help="Attribute of the source features holding the area name",
        )

    def handle(self, *args, **options) -> None:
        path = options["path"]
        # LayerMapping wants the source geometry type; read it from the layer instead of
        # hardcoding it per file. Polygons are promoted to the MultiPolygon model field.
        geom_type = DataSource(path)[0].geom_type.name.upper()
        mapping = {"name": options["name_field"], "mpoly": geom_type}
        LayerMapping(Area, path, mapping).save(verbose=True)
