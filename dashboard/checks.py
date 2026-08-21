"""Django system checks for the dashboard app."""

from django.core.checks import Warning
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
