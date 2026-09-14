"""Authentication helpers for the v2 API."""
import datetime

from django.http import HttpRequest
from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import HttpBearer

from dashboard.models import ApiToken

# How stale last_used_at may be before an authenticated request refreshes it.
LAST_USED_REFRESH = datetime.timedelta(minutes=5)


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
        # Session auth drops inactive users in authenticate(); a token must not
        # be the back door around deactivation. The token itself is kept, so
        # reactivating the account restores it.
        if not obj.user.is_active:
            raise HttpError(401, "Invalid API token")
        # last_used_at is a coarse "is this token still in use" signal for the
        # tokens page. Refresh it at most once per window rather than on every
        # request, so a script hitting the API in a loop does not turn each
        # request into a write.
        now = timezone.now()
        if obj.last_used_at is None or now - obj.last_used_at > LAST_USED_REFRESH:
            ApiToken.objects.filter(pk=obj.pk).update(last_used_at=now)
        # Downstream endpoints read request.user; make the token act as its owner.
        request.user = obj.user
        return obj.user
