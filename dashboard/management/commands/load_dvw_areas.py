"""Custom script to import the DVW areas for the LIFE RIPARIAS project.

The usual load_area.py script cannot be used because the specifities of the data make it unsuitable for the usual
LayerMapping helper.

See task description at: https://github.com/riparias/early-alert-webapp/issues/8
"""
import os

from django.contrib.gis.gdal import DataSource, SpatialReference, CoordTransform
from django.contrib.gis.gdal.feature import Feature
from django.contrib.gis.gdal.geometries import MultiPolygon, OGRGeometry
from django.core.management import BaseCommand

from dashboard.models import Area, DATA_SRID

THIS_FILE_DIR = os.path.dirname(__file__)
SOURCE_DATA_STRID = SpatialReference("EPSG:4326")

ct = CoordTransform(SOURCE_DATA_STRID, SpatialReference(f"EPSG:{DATA_SRID}"))

DVW_SOURCE_DATA: dict[str, dict] = {
    "Districts": {
        "path": f"{THIS_FILE_DIR}/../../../source_data/public_areas/dvw/Districts/Districts.shp",
        "name_field": "DSTRCT",
        "tags": ["DVW", "district"],
        "dynamic_tag_field": "AFD",
    },
    "Core sectors": {
        "path": f"{THIS_FILE_DIR}/../../../source_data/public_areas/dvw/Sector_core/Sector_core.shp",
        "name_field": "SCTR",
        "tags": ["DVW", "sector", "core"],
        "dynamic_tag_field": "AFD",
    },
    "Extended sectors": {
        "path": f"{THIS_FILE_DIR}/../../../source_data/public_areas/dvw/Sector_extended/Sector_extended.shp",
        "name_field": "SCTR",
        "tags": ["DVW", "sector", "extended"],
        "dynamic_tag_field": "AFD",
    },
    "Sector parcels": {
        "path": f"{THIS_FILE_DIR}/../../../source_data/public_areas/dvw/Sector_parcels/Sector_parcels.shp",
        "name_field": "SCTR",
        "tags": ["DVW", "parcel"],
        "dynamic_tag_field": "AFD",
    },
}


def get_multipolygon_from_feature(feature: Feature) -> OGRGeometry:
    """Return a WKT representation of the feature's geometry.

    If the feature is a MultiPolygon, the MultiPolygon is returned.
    If the feature is a Polygon, a MultiPolygon with a single Polygon is returned.
    """
    if feature.geom_type.name == "MultiPolygon":
        return feature.geom
    elif feature.geom_type.name == "Polygon":
        m = MultiPolygon("MULTIPOLYGON EMPTY")
        m.add(feature.geom)
        return m
    else:
        raise ValueError(f"Unexpected geometry type: {feature.geom_type.name}")


class Command(BaseCommand):
    help = "Import DWV areas in the database."

    def handle(self, *args, **options) -> None:
        self.stdout.write("Importing DVW areas")
        for layer_name, layer_config in DVW_SOURCE_DATA.items():
            self.stdout.write(f"Importing layer {layer_name}")

            ds = DataSource(layer_config["path"])
            layer = ds[0]
            self.stdout.write(f"Found {layer.num_feat} features")  # type: ignore
            for feature in layer:
                area_name = feature[layer_config["name_field"]]  # type: ignore
                tags = layer_config["tags"].copy()
                tags.append(feature[layer_config["dynamic_tag_field"]].value)  # type: ignore

                self.stdout.write(f"Creating area {area_name}, with tags {tags}")

                multipolygon = get_multipolygon_from_feature(feature)
                reprojected_multipolygon = multipolygon.transform(ct, clone=True)

                area = Area.objects.create(mpoly=reprojected_multipolygon.wkt, name=area_name)  # type: ignore
                area.tags.add(*tags)
