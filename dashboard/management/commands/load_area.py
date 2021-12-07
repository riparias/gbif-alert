import os
import sys

from django.contrib.gis.utils import LayerMapping
from django.core.management import BaseCommand, CommandParser

from dashboard.models import Area

THIS_DIR = os.path.dirname(__file__)

SOURCE_DIRECTORY = os.path.join(THIS_DIR, "../../../source_data/global_areas")

LAYER_MAPPING_CONFIGURATION = {  # key: filename / value: mapping
    "Riparias_Official_StudyArea.geojson": {"name": "BEKNAAM", "mpoly": "POLYGON"}
}


class Command(BaseCommand):
    help = (
        "Import new predefined areas in the database. "
        ""
        "Takes a single argument: source data file name (in source_data/global_areas). "
        "This script should be adjusted (mapping, projections, ...) for each area data source"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "area-source-filename",
            help="Source data file name",
        )

    def handle(self, *args, **options) -> None:
        self.stdout.write("Loading an area (from file in static/areas)")

        filename = options["area-source-filename"]
        try:
            mapping = LAYER_MAPPING_CONFIGURATION[filename]
            self.stdout.write(f"Mapping found for {filename}")
        except KeyError:
            self.stdout.write(
                f"No mapping found for {filename}, is the filename correct. Has the script been adjusted "
                f"for this data source?"
            )
            sys.exit(1)

        lm = LayerMapping(Area, os.path.join(SOURCE_DIRECTORY, filename), mapping)
        lm.save(verbose=True)