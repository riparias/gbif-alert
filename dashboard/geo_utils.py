import json

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.gdal.geometries import MultiPolygon
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon as GEOSMultiPolygon

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


def geojson_to_multipolygon(
    geojson: dict,
    dest_srid: int = DATA_SRID,
) -> GEOSMultiPolygon:
    """Convert a GeoJSON FeatureCollection (EPSG:4326) to a GEOSMultiPolygon.

    Parameters
    ----------
    geojson : dict
        A GeoJSON FeatureCollection with Polygon or MultiPolygon features,
        in EPSG:4326. This is the format produced by the OpenLayers GeoJSON
        format class.
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
        If the FeatureCollection contains no features, or contains a geometry
        type other than Polygon or MultiPolygon.
    """
    features = geojson.get("features", [])
    if not features:
        raise ValueError("GeoJSON FeatureCollection must contain at least one feature")

    polygons = []
    for feature in features:
        geom = GEOSGeometry(json.dumps(feature["geometry"]), srid=4326)
        geom.transform(dest_srid)
        if geom.geom_type == "Polygon":
            polygons.append(geom)
        elif geom.geom_type == "MultiPolygon":
            polygons.extend(list(geom))  # type: ignore[call-overload]  # MultiPolygon is iterable at runtime
        else:
            raise ValueError(
                f"Expected Polygon or MultiPolygon features, got {geom.geom_type}"
            )

    return GEOSMultiPolygon(*polygons, srid=dest_srid)
