import json

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.gdal.geometries import MultiPolygon
from django.contrib.gis.geos import (
    GEOSException,
    GEOSGeometry,
    MultiPolygon as GEOSMultiPolygon,
)

from dashboard.models import DATA_SRID


def file_to_wkt_multipolygon(
    data_path: str,
    dest_srid: int = DATA_SRID,
) -> str:
    """Convert a GIS file to a WKT MultiPolygon string reprojected to dest_srid.

    Parameters
    ----------
    data_path : str
        Path to a GIS file (e.g. GeoPackage) on the local filesystem.
    dest_srid : int
        Target SRID for the output geometry. Defaults to DATA_SRID (3857).

    Returns
    -------
    str
        WKT representation of the (multi)polygon reprojected to dest_srid.

    Raises
    ------
    ValueError
        If the file has more than one layer, more than one feature, no SRS,
        or a geometry type other than Polygon or MultiPolygon.
    """
    ds = DataSource(data_path)
    if ds.layer_count != 1:
        raise ValueError(
            f"The file must contain a single layer, {ds.layer_count} layers found"
        )
    layer = ds[0]

    num_feat = layer.num_feat  # type: ignore
    if num_feat != 1:
        raise ValueError(
            f"The file must contain a single feature, {num_feat} features found"
        )

    if layer.srs is None:
        raise ValueError(
            "The file does not contain a SRS, please provide a file with a SRS"
        )

    feature = list(layer)[0]
    reprojected_geom = feature.geom.transform(dest_srid, clone=True)

    if layer.geom_type.name == "MultiPolygon":
        return reprojected_geom.wkt
    elif layer.geom_type.name == "Polygon":
        m = MultiPolygon("MULTIPOLYGON EMPTY")
        m.add(reprojected_geom)
        return m.wkt
    else:
        raise ValueError(
            f"The file must contain a single layer of type Polygon or MultiPolygon, "
            f"{layer.geom_type.name} found"
        )


def _geometries_from_geojson(geojson: dict) -> list[dict]:
    """Normalise accepted GeoJSON shapes to a flat list of geometry dicts.

    Accepts a FeatureCollection, a single Feature, or a bare Polygon /
    MultiPolygon geometry. Scripts commonly hold one of the latter two (a row
    from a fiona iteration, or the output of shapely.geometry.mapping), so
    rejecting them would only force every caller to write the same wrapper.

    Parameters
    ----------
    geojson : dict
        Parsed GeoJSON object.

    Returns
    -------
    list of dict
        The geometry members, in document order.

    Raises
    ------
    ValueError
        If the object is not a dict, has an unsupported type, contains no
        features, or contains a feature without a geometry.
    """
    if not isinstance(geojson, dict):
        raise ValueError("GeoJSON must be an object")

    geojson_type = geojson.get("type")

    if geojson_type == "FeatureCollection":
        features = geojson.get("features") or []
        if not features:
            raise ValueError(
                "GeoJSON FeatureCollection must contain at least one feature"
            )
        geometries = []
        for feature in features:
            geometry = (feature or {}).get("geometry")
            if not geometry:
                raise ValueError("A GeoJSON Feature has no geometry")
            geometries.append(geometry)
        return geometries

    if geojson_type == "Feature":
        geometry = geojson.get("geometry")
        if not geometry:
            raise ValueError("A GeoJSON Feature has no geometry")
        return [geometry]

    if geojson_type in ("Polygon", "MultiPolygon"):
        return [geojson]

    raise ValueError(
        f"Unsupported GeoJSON type: {geojson_type!r}. Expected a "
        f"FeatureCollection, a Feature, or a Polygon / MultiPolygon geometry"
    )


def geojson_to_multipolygon(
    geojson: dict,
    dest_srid: int = DATA_SRID,
) -> GEOSMultiPolygon:
    """Convert a GeoJSON FeatureCollection (EPSG:4326) to a GEOSMultiPolygon.

    Parameters
    ----------
    geojson : dict
        A GeoJSON FeatureCollection, a single Feature, or a bare Polygon /
        MultiPolygon geometry, in EPSG:4326. The FeatureCollection form is what
        the OpenLayers GeoJSON format class produces.
    dest_srid : int
        Target SRID for the returned geometry. Defaults to DATA_SRID (3857).

    Returns
    -------
    GEOSMultiPolygon
        A MultiPolygon geometry in dest_srid containing all polygons from the
        input features.

    Raises
    ------
    ValueError
        If the input is not a supported GeoJSON shape, contains no features,
        has a feature without a geometry, contains a geometry type other than
        Polygon or MultiPolygon, or has coordinates GEOS cannot parse.
    """
    polygons = []
    for geometry in _geometries_from_geojson(geojson):
        try:
            geom = GEOSGeometry(json.dumps(geometry), srid=4326)
            geom.transform(dest_srid)
        except (GEOSException, GDALException, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid geometry: {exc}") from exc

        if geom.geom_type == "Polygon":
            polygons.append(geom)
        elif geom.geom_type == "MultiPolygon":
            polygons.extend(list(geom))  # type: ignore[call-overload]  # MultiPolygon is iterable at runtime
        else:
            raise ValueError(
                f"Expected Polygon or MultiPolygon features, got {geom.geom_type}"
            )

    return GEOSMultiPolygon(*polygons, srid=dest_srid)
