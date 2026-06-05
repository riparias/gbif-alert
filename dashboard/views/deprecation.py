"""Helpers for marking legacy endpoints deprecated.

The legacy public `/api/*` JSON endpoints have v2 successors under `/api/v2/`.
API v2 is now the supported, public HTTP API. The legacy endpoints are
deprecated per RFC 8594: each response carries a `Deprecation` flag, a `Link`
to its successor (RFC 8288), and a `Sunset` date marking when the endpoint will
be removed. They keep working until that date so consumers can migrate at their
own pace.
"""
from datetime import date, datetime, timezone
from email.utils import format_datetime
from functools import wraps
from typing import Callable

from django.http import HttpRequest, HttpResponse

# The date on which the legacy /api/* JSON endpoints will be removed. Communicated
# to consumers via the Sunset header and on the /api-docs page. Picked to give a
# generous ~12 months of notice (decided 2026-06, known external consumers exist).
LEGACY_API_SUNSET = date(2027, 6, 30)


def _http_date(day: date) -> str:
    """Format a date as an RFC 7231 HTTP-date at UTC midnight (for ``Sunset``)."""
    moment = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return format_datetime(moment, usegmt=True)


def deprecated_endpoint(successor: str) -> Callable:
    """Mark a view's responses deprecated, pointing at its v2 successor.

    Adds three response headers:
    - ``Deprecation: true`` (RFC 8594)
    - ``Link: <successor>; rel="successor-version"`` (RFC 8288)
    - ``Sunset: <http-date>`` (RFC 8594), using :data:`LEGACY_API_SUNSET`

    Parameters
    ----------
    successor : str
        The path of the v2 endpoint that replaces this one, e.g.
        ``/api/v2/observations/counter/``.
    """

    def decorator(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            response = view(request, *args, **kwargs)
            response["Deprecation"] = "true"
            response["Link"] = f'<{successor}>; rel="successor-version"'
            response["Sunset"] = _http_date(LEGACY_API_SUNSET)
            return response

        return wrapper

    return decorator
