"""Django system checks for the dashboard app."""

from typing import cast

from django.conf import settings
from django.contrib.gis.geos import (
    GEOSException,
    GEOSGeometry,
    MultiPolygon,
    Polygon,
)
from django.core.checks import Error, Warning
from django.db import OperationalError, ProgrammingError

from dashboard.models import Area


def check_areas_have_parts(app_configs, **kwargs) -> list[Warning]:
    """Warn about areas with no AreaPart rows.

    The observation area filter joins AreaPart and has no fallback to the old
    whole-geometry query, so an area without parts silently matches nothing.
    Area.save() keeps them in sync; this catches areas created by paths that
    bypass it.
    """
    try:
        orphans = list(
            Area.objects.filter(parts__isnull=True).values_list("id", "name")[:10]
        )
        count = Area.objects.filter(parts__isnull=True).count()
    except (OperationalError, ProgrammingError):
        # The table does not exist yet (fresh database, before migrate).
        return []

    if not orphans:
        return []

    listed = ", ".join(f"#{pk} {name}" for pk, name in orphans)
    suffix = ", ..." if count > len(orphans) else ""
    return [
        Warning(
            f"{count} area(s) have no subdivided parts and will match no "
            f"observations: {listed}{suffix}",
            hint="Run `python manage.py rebuild_area_parts`.",
            id="dashboard.W001",
        )
    ]


def check_download_geometry(app_configs, **kwargs) -> list[Error]:
    """Reject a `GBIF_DOWNLOAD_GEOMETRY` that GBIF would refuse or misread.

    The value is long and pasted by hand, so a cut-short paste is the likely
    accident. The winding order matters more: GBIF wants exterior rings
    anticlockwise and holes clockwise, and reads a clockwise exterior ring as
    "everything outside the polygon" - a download of the rest of the world,
    with no error from GBIF.
    """
    wkt = settings.GBIF_DOWNLOAD_GEOMETRY
    if not wkt:
        return []

    def error(problem: str) -> list[Error]:
        return [Error(f"GBIF_DOWNLOAD_GEOMETRY {problem}", id="dashboard.E001")]

    try:
        geometry = GEOSGeometry(wkt)
    except (GEOSException, ValueError):
        return error("is not valid WKT (was the value cut short when pasted?).")

    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        # The stubs type a MultiPolygon's members as plain GEOSGeometry.
        polygons = cast(list[Polygon], list(geometry))
    else:
        return error(f"must be a Polygon or MultiPolygon, got {geometry.geom_type}.")
    if not geometry.valid:
        return error(f"is an invalid geometry: {geometry.valid_reason}.")

    for polygon in polygons:
        exterior, *holes = polygon
        if not exterior.is_counterclockwise or any(
            hole.is_counterclockwise for hole in holes
        ):
            return error(
                "must have anticlockwise exterior rings and clockwise holes: "
                "GBIF reads a clockwise exterior ring as everything outside it."
            )
    return []
