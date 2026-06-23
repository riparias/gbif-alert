"""Import-set maintenance-mode tagging and self-heal.

`import_observations` puts the site in maintenance mode while it rebuilds the
materialized views inside its transaction. The import runs via ofelia job-exec
inside the web container; a redeploy SIGKILLs it mid-flight, and the command's
`finally` clears maintenance only on a Python exception, not on SIGKILL - so an
interrupted import can strand the site in maintenance mode.

To recover without cancelling a manually enabled maintenance window, the import
tags its maintenance with a marker cache key. On web-container startup,
`clear_stale_import_maintenance()` clears maintenance only when that marker is
present (an import set it and was killed before clearing).

Assumes a single web replica: the import runs inside the web container, so a
starting web container means any import that set the marker is already dead. If
the web service is ever scaled to more than one replica this invariant weakens.
"""
import logging

from django.core.cache import cache
from maintenance_mode.core import (  # type: ignore
    get_maintenance_mode,
    set_maintenance_mode,
)

logger = logging.getLogger(__name__)

# Cache key (same cache as the maintenance state) marking maintenance as import-set.
MAINTENANCE_IMPORT_MARKER = "maintenance_set_by_import"


def enable_maintenance_for_import() -> None:
    """Enable maintenance mode and tag it as import-set."""
    set_maintenance_mode(True)
    cache.set(MAINTENANCE_IMPORT_MARKER, True, None)


def disable_maintenance_for_import() -> None:
    """Disable maintenance mode and drop the import marker."""
    set_maintenance_mode(False)
    cache.delete(MAINTENANCE_IMPORT_MARKER)


def clear_stale_import_maintenance() -> None:
    """Clear maintenance left stranded by a killed import; leave manual windows alone.

    - maintenance ON + marker present -> killed import; clear both.
    - maintenance ON + no marker      -> manually enabled; leave it.
    - maintenance OFF                 -> drop any leftover marker; do nothing else.

    Wrapped so a cache error at boot logs a warning instead of blocking startup.
    """
    try:
        if get_maintenance_mode():
            if cache.get(MAINTENANCE_IMPORT_MARKER):
                set_maintenance_mode(False)
                cache.delete(MAINTENANCE_IMPORT_MARKER)
                logger.warning(
                    "Cleared stranded import-set maintenance mode on startup."
                )
            else:
                logger.info(
                    "Maintenance mode is on but not import-set; leaving it untouched."
                )
        else:
            cache.delete(MAINTENANCE_IMPORT_MARKER)
    except Exception as exc:  # noqa: BLE001 - boot must not be blocked by a cache hiccup
        logger.warning(
            "clear_stale_import_maintenance skipped due to error: %r", exc
        )
