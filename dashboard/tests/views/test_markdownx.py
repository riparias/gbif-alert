"""The markdownx endpoints exist only for the admin's PageFragment editor.

markdownx ships them without any authentication, so mounted as-is the upload
view lets any anonymous visitor write files into media storage. They are
wrapped in staff_member_required in djangoproject/urls.py; these tests pin
that, and that the url names the admin widget resolves still exist.
"""

import base64

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.django_db

# A 1x1 transparent PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _upload(client):
    return client.post(
        reverse("markdownx_upload"),
        {"image": SimpleUploadedFile("x.png", _PNG, content_type="image/png")},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )


def _markdownify(client):
    return client.post(
        reverse("markdownx_markdownify"),
        {"content": "# hi"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def _files_in(root):
    return [p for p in root.rglob("*") if p.is_file()]


def test_anonymous_upload_is_refused_and_writes_nothing(client, media_root):
    response = _upload(client)
    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login"))
    assert _files_in(media_root) == []


def test_non_staff_user_upload_is_refused_and_writes_nothing(client, media_root):
    user = get_user_model().objects.create_user(
        username="plain", password="pass", email="plain@test.com"
    )
    client.force_login(user)
    response = _upload(client)
    assert response.status_code == 302
    assert _files_in(media_root) == []


def test_staff_upload_works(client, media_root):
    staff = get_user_model().objects.create_user(
        username="staff", password="pass", email="staff@test.com", is_staff=True
    )
    client.force_login(staff)
    response = _upload(client)
    assert response.status_code == 200
    assert "image_code" in response.json()
    assert len(_files_in(media_root)) == 1


def test_anonymous_markdownify_is_refused(client):
    response = _markdownify(client)
    assert response.status_code == 302


def test_staff_markdownify_works(client):
    staff = get_user_model().objects.create_user(
        username="staff", password="pass", email="staff@test.com", is_staff=True
    )
    client.force_login(staff)
    response = _markdownify(client)
    assert response.status_code == 200
    assert b"<h1" in response.content
