from django.contrib.gis.gdal.feature import Feature
from django.contrib.gis.gdal.geometries import MultiPolygon, OGRGeometry

import requests

from dashboard.models import Dataset

# Enough for a single registry lookup, short enough that an unresponsive GBIF
# API cannot stall a whole import.
_GBIF_API_TIMEOUT_SECONDS = 30


def get_dataset_name_from_gbif_api(gbif_dataset_key: str) -> str:
    """Return the dataset title held by the GBIF registry, or "" if unavailable.

    Occurrence downloads carry dwc:datasetName, the *verbatim* name supplied by
    the publisher, which most publishers leave empty. The registry title is the
    only reliable source of a human-readable dataset name.

    This is a best-effort, cosmetic lookup: a network problem or an unknown key
    yields "" rather than an exception, so it can never abort its caller.
    """
    query_url = f"https://api.gbif.org/v1/dataset/{gbif_dataset_key}"

    try:
        response = requests.get(query_url, timeout=_GBIF_API_TIMEOUT_SECONDS)
        return response.json().get("title", "") or ""
    except (requests.RequestException, ValueError):
        # ValueError covers a non-JSON body (json.JSONDecodeError subclasses it).
        return ""


def fill_missing_dataset_names(stdout=None) -> int:
    """Give every unnamed Dataset the title the GBIF registry holds for its key.

    Returns the number of datasets actually named. Datasets that already have a
    name are left untouched: the registry is only consulted for the blanks.

    Meant to run outside the import transaction - the names are cosmetic, and a
    slow or failing GBIF API must not hold a write transaction open or roll an
    otherwise good import back.
    """
    updated = 0
    for dataset in Dataset.objects.filter(name=""):
        try:
            name = get_dataset_name_from_gbif_api(dataset.gbif_dataset_key)
        except Exception as exc:
            # Defensive: one unexpected error must not leave the rest unnamed.
            _log(stdout, f"Could not name dataset {dataset.gbif_dataset_key}: {exc!r}")
            continue

        if name:
            dataset.name = name
            dataset.save(update_fields=["name"])
            updated += 1
            _log(stdout, f"Named dataset {dataset.gbif_dataset_key}: {name}")

    return updated


def _log(stdout, message: str) -> None:
    if stdout is not None:
        stdout.write(message)


def get_multipolygon_from_feature(feature: Feature) -> OGRGeometry:
    """Return a WKT representation of the feature's geometry.

    If the feature is a MultiPolygon, the MultiPolygon is returned.
    If the feature is a Polygon, a MultiPolygon with a single Polygon is returned.
    """
    if (feature.geom_type.name == "MultiPolygon") or (
        feature.geom_type.name == "Unknown" and feature.geom.geom_name == "MULTIPOLYGON"
    ):
        return feature.geom
    elif feature.geom_type.name == "Polygon":
        m = MultiPolygon("MULTIPOLYGON EMPTY")
        m.add(feature.geom)
        return m
    else:
        raise ValueError(f"Unexpected geometry type: {feature.geom_type.name}")


def remove_z_dimension(geom: OGRGeometry) -> OGRGeometry:
    copy = geom.clone()
    copy.coord_dim = 2
    return copy
