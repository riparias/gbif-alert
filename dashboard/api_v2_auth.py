"""Authentication helpers for the v2 API."""
from django.http import HttpRequest
from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import HttpBearer

from dashboard.models import ApiToken


class ApiTokenAuth(HttpBearer):
    """Authenticate a request from a personal access token (Authorization: Bearer).

    Used alongside session auth as `auth=[ApiTokenAuth(), django_auth]`. It must
    be listed FIRST: HttpBearer returns None when there is no Authorization
    header, so session requests fall through to django_auth (and its CSRF check),
    while token requests are handled here without CSRF. A present-but-invalid
    token raises 401 rather than returning None, so it never falls through to the
    session authenticator (whose CSRF check would otherwise turn it into a 403).
    """

    def authenticate(self, request: HttpRequest, token: str):
        obj = (
            ApiToken.objects.filter(token_hash=ApiToken.hash_token(token))
            .select_related("user")
            .first()
        )
        if obj is None:
            raise HttpError(401, "Invalid API token")
        ApiToken.objects.filter(pk=obj.pk).update(last_used_at=timezone.now())
        # Downstream endpoints read request.user; make the token act as its owner.
        request.user = obj.user
        return obj.user
