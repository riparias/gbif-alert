"""Helpers for marking legacy endpoints deprecated.

The legacy public `/api/*` JSON endpoints have v2 successors under `/api/v2/`.
We signal their deprecation per RFC 8594, but deliberately do NOT set a `Sunset`
removal date yet: the removal timeline depends on the still-open public-API
governance decision. Consumers get the `Deprecation` flag and a link to the
successor so they can migrate at their own pace.
"""
from functools import wraps
from typing import Callable

from django.http import HttpRequest, HttpResponse


def deprecated_endpoint(successor: str) -> Callable:
    """Mark a view's responses deprecated, pointing at its v2 successor.

    Adds two response headers:
    - ``Deprecation: true`` (RFC 8594)
    - ``Link: <successor>; rel="successor-version"`` (RFC 8288)

    No ``Sunset`` header is set - see the module docstring.

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
            return response

        return wrapper

    return decorator
