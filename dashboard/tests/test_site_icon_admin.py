"""Tests for uploading the site icon through the Django admin."""
from io import BytesIO

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse, reverse_lazy
from PIL import Image

from dashboard.admin import SiteIconAdmin, SiteIconForm
from dashboard.models import SiteIcon

ADD_URL = reverse_lazy("admin:dashboard_siteicon_add")
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def _image_bytes(file_format, size=(100, 100)):
    """Return an image file's content. Noise keeps truncated JPEGs decodable."""
    buffer = BytesIO()
    Image.effect_noise(size, 80).convert("RGB").save(buffer, file_format)
    return buffer.getvalue()


def _form(name, content):
    return SiteIconForm(data={}, files={"upload": SimpleUploadedFile(name, content)})


def _stored_image():
    return Image.open(BytesIO(bytes(SiteIcon.objects.get().png)))


def _site_icon_admin():
    return SiteIconAdmin(SiteIcon, AdminSite())


@pytest.mark.django_db
def test_wide_logo_is_padded_to_a_square():
    """A wide project logo keeps its proportions, with transparent margins.

    A wide logo is the likely first upload, and browsers would otherwise show a
    non-square icon squashed or cropped, depending on the browser.
    """
    form = _form("logo.png", _image_bytes("PNG", size=(1000, 400)))
    assert form.is_valid()
    form.save()

    stored = _stored_image()
    assert stored.size == (512, 512)
    assert stored.convert("RGBA").getpixel((0, 0))[3] == 0
    assert stored.convert("RGBA").getpixel((256, 256))[3] == 255


@pytest.mark.django_db
def test_small_icon_is_not_upscaled():
    """A small icon stays at its own size.

    Enlarging it would add bytes and blur without adding any detail.
    """
    form = _form("icon.png", _image_bytes("PNG", size=(64, 64)))
    assert form.is_valid()
    form.save()

    assert _stored_image().size == (64, 64)


@pytest.mark.django_db
def test_ico_upload_is_accepted():
    """An existing favicon.ico works: it is what many operators already have."""
    form = _form("favicon.ico", _image_bytes("ICO", size=(64, 64)))
    assert form.is_valid()
    form.save()

    assert _stored_image().format == "PNG"


@pytest.mark.django_db
def test_stored_bytes_are_always_png():
    """Whatever the upload format, only a PNG is stored and served.

    The icon view always answers image/png, and re-encoding guarantees the site
    never serves a file exactly as it was uploaded.
    """
    form = _form("logo.jpg", _image_bytes("JPEG"))
    assert form.is_valid()
    form.save()

    assert _stored_image().format == "PNG"


@pytest.mark.django_db
def test_svg_is_rejected():
    """SVG uploads are refused and nothing is stored.

    An SVG served from the site's own domain can run scripts, so it must never
    reach the icon URL.
    """
    form = _form("logo.svg", SVG)

    assert not form.is_valid()
    assert "upload" in form.errors
    assert not SiteIcon.objects.exists()


@pytest.mark.django_db
def test_truncated_jpeg_is_rejected():
    """A damaged JPEG gives a form error rather than a server error.

    It gets past forms.ImageField, which only checks the header, and fails when
    decoded: without handling, the admin would show a 500 page.
    """
    form = _form("logo.jpg", _image_bytes("JPEG", size=(300, 300))[:2000])

    assert not form.is_valid()
    assert "upload" in form.errors


@pytest.mark.django_db
def test_huge_image_is_rejected():
    """An image with enormous dimensions gets a form error.

    forms.ImageField does not decode the pixels, and a few KB of PNG can declare
    a size that needs gigabytes once decoded. One such upload could get a web
    worker killed, so the size is checked before decoding.
    """
    form = _form("huge.png", _image_bytes("PNG", size=(4097, 10)))

    assert not form.is_valid()
    assert "upload" in form.errors


@pytest.mark.django_db
def test_upload_through_the_admin_page_stores_the_icon(admin_client):
    """The real admin page accepts a file and stores the icon.

    Covers what the form tests cannot: the page is a multipart form and shows
    the upload field, so an operator can actually use it.
    """
    response = admin_client.post(
        reverse("admin:dashboard_siteicon_add"),
        {"upload": SimpleUploadedFile("icon.png", _image_bytes("PNG"))},
    )

    assert response.status_code == 302
    assert _stored_image().size == (100, 100)


@pytest.mark.django_db
def test_replacing_the_icon_keeps_a_single_row(admin_client):
    """Uploading on the existing row replaces the icon.

    The view reads the first row, so a second row would be silently ignored.
    """
    icon = SiteIcon.objects.create(png=b"old")

    response = admin_client.post(
        reverse("admin:dashboard_siteicon_change", args=[icon.pk]),
        {"upload": SimpleUploadedFile("icon.png", _image_bytes("PNG"))},
    )

    assert response.status_code == 302
    assert _stored_image().size == (100, 100)


@pytest.mark.django_db
def test_first_icon_can_be_added(admin_client):
    """An instance without an icon can add one."""
    assert admin_client.get(ADD_URL).status_code == 200


@pytest.mark.django_db
def test_second_icon_cannot_be_added(admin_client):
    """Once an icon exists, the admin offers replacing it, not adding another.

    A second row would never be served, so the upload would look broken.
    """
    SiteIcon.objects.create(png=b"icon")

    assert admin_client.get(ADD_URL).status_code == 403


@pytest.mark.django_db
def test_staff_without_permission_cannot_add_an_icon(client, django_user_model):
    """Being staff is not enough to change the icon every visitor sees.

    The single-row rule must narrow Django's permission check, not replace it:
    an account limited to other admin pages must get a 403 here too.
    """
    staff = django_user_model.objects.create_user(
        username="staff", password="pass", email="staff@e.com", is_staff=True
    )
    client.force_login(staff)

    assert client.get(ADD_URL).status_code == 403


@pytest.mark.django_db
def test_deleting_the_icon_restores_the_default(admin_client):
    """Deleting the row is how an operator goes back to the default icon.

    There is no other way back, so it must stay allowed in the admin.
    """
    icon = SiteIcon.objects.create(png=b"icon")

    admin_client.post(
        reverse("admin:dashboard_siteicon_delete", args=[icon.pk]), {"post": "yes"}
    )

    assert not SiteIcon.objects.exists()
    assert admin_client.get("/site-icon.png").status_code == 302


@pytest.mark.django_db
def test_preview_url_changes_with_the_icon():
    """The preview URL carries the update time.

    The icon URL is cached for a day, so without this the operator would see
    the old icon in the preview right after replacing it.
    """
    icon = SiteIcon.objects.create(png=b"icon")
    first_preview = _site_icon_admin().preview(icon)

    icon.save()

    assert "/site-icon.png?v=" in first_preview
    assert _site_icon_admin().preview(icon) != first_preview


def test_preview_is_empty_before_the_first_upload():
    """The add page has no icon to show yet, and must not crash on that."""
    assert _site_icon_admin().preview(SiteIcon()) == "-"
