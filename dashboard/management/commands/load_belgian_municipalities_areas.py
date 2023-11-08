"""Custom script to import the municipalities (Belgium) for the LIFE RIPARIAS project.

The usual load_area.py script cannot be used because the specifics of the data make it unsuitable for the usual
LayerMapping helper.

See task description at: https://github.com/riparias/early-alert-webapp/issues/18
"""

import os

from django.contrib.gis.gdal import DataSource, SpatialReference, CoordTransform
from django.core.management import BaseCommand

from dashboard.management.commands.helpers import (
    get_multipolygon_from_feature,
    remove_z_dimension,
)
from dashboard.models import Area, DATA_SRID

THIS_FILE_DIR = os.path.dirname(__file__)
SOURCE_DATA_STRID = SpatialReference("EPSG:4326")

ct = CoordTransform(SOURCE_DATA_STRID, SpatialReference(f"EPSG:{DATA_SRID}"))

SOURCE_DATA: dict[str, dict] = {
    "Municipalities": {
        "path": f"{THIS_FILE_DIR}/../../../source_data/public_areas/belgian_municipalities/adminvector_4326.gpkg",
    },
}


class Command(BaseCommand):
    help = "Import river areas from Wallonia in the database."

    def handle(self, *args, **options) -> None:
        for layer_name, layer_config in SOURCE_DATA.items():
            self.stdout.write(f"Importing layer {layer_name}")

            ds = DataSource(layer_config["path"])
            for layer in ds:
                if layer.name == "municipality":
                    self.stdout.write(f"Found {layer.num_feat} features")  # type: ignore
                    for feature in layer:
                        tags = ["municipality"]
                        language_statute = feature["languagestatute"].value
                        match language_statute:
                            case 1:
                                area_name = feature["namedut"].value
                                tags.append("Flanders")
                            case 2:
                                area_name = feature["namefre"].value
                                tags.append("Wallonia")
                            case 4:
                                area_name = f"{feature['namedut'].value} - {feature['namefre'].value}"
                                tags.append("Brussels")
                            case 5:
                                area_name = feature["namedut"].value
                                tags.append("Flanders")
                            case 6:
                                area_name = feature["namefre"].value
                                tags.append("Wallonia")
                            case 7:
                                area_name = feature["namefre"].value
                                tags.append("Wallonia")
                            case 8:
                                area_name = feature["nameger"].value
                                tags.append("Wallonia")

                        multipolygon = remove_z_dimension(
                            get_multipolygon_from_feature(feature)
                        )
                        reprojected_multipolygon = multipolygon.transform(
                            ct, clone=True
                        )

                        self.stdout.write(
                            f"Creating area {area_name}, with tags {tags}"
                        )
                        area = Area.objects.create(mpoly=reprojected_multipolygon.wkt, name=area_name)  # type: ignore
                        area.tags.add(*tags)
