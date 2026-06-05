import pytest
from django.contrib.admin.sites import site
from django.test import override_settings

from dashboard.admin import ApiTokenAdmin
from dashboard.models import ApiToken

pytestmark = pytest.mark.django_db


def test_api_token_admin_is_read_only():
    """Tokens can't be created or edited through the admin."""
    ma = ApiTokenAdmin(ApiToken, site)
    assert ma.has_add_permission(None) is False
    assert ma.has_change_permission(None) is False


# Render the admin with plain static storage: CI has no collectstatic manifest,
# so the manifest-based ViteAwareStaticStorage would fail on admin/css/base.css.
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
def test_api_token_admin_changelist_and_revoke(client, django_user_model):
    """A superuser can view tokens and revoke (delete) them; adding is blocked."""
    admin = django_user_model.objects.create_superuser("adm", "adm@e.com", "pw")
    user = django_user_model.objects.create_user("tu", "tu@e.com", "pw")
    token, _ = ApiToken.create_for(user, "some token")
    client.force_login(admin)

    # The list view is accessible (read-only).
    assert client.get("/admin/dashboard/apitoken/").status_code == 200
    # Creating is forbidden.
    assert client.get("/admin/dashboard/apitoken/add/").status_code == 403
    # Revoking (deleting) works.
    resp = client.post(
        f"/admin/dashboard/apitoken/{token.pk}/delete/", {"post": "yes"}
    )
    assert resp.status_code == 302
    assert not ApiToken.objects.filter(pk=token.pk).exists()
