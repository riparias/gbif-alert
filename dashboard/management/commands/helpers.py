from functools import cache

from django.contrib.gis.gdal.feature import Feature
from django.contrib.gis.gdal.geometries import MultiPolygon, OGRGeometry

import requests


@cache
def get_dataset_name_from_gbif_api(gbif_dataset_key: str) -> str:
    query_url = f"https://api.gbif.org/v1/dataset/{gbif_dataset_key}"

    dataset_details = requests.get(query_url).json()
    return dataset_details["title"]


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
