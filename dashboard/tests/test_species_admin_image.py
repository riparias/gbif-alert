import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from dashboard.admin import SpeciesAdmin
from dashboard.models import Species

User = get_user_model()


class _Form:
    def __init__(self, changed):
        self.changed_data = changed


@pytest.mark.django_db
def test_admin_manual_url_sets_provenance_manual():
    sp = Species(name="Testus specius", gbif_taxon_key=999020,
                 image_url="https://example.org/x.jpg")
    admin = SpeciesAdmin(Species, AdminSite())
    admin.save_model(request=None, obj=sp, form=_Form(["image_url"]), change=False)
    sp.refresh_from_db()
    assert sp.image_source_type == "manual"


@pytest.mark.django_db
def test_admin_clearing_url_resets_provenance():
    sp = Species(name="Testus specius", gbif_taxon_key=999021,
                 image_url="", image_source_type="wikipedia")
    admin = SpeciesAdmin(Species, AdminSite())
    admin.save_model(request=None, obj=sp, form=_Form(["image_url"]), change=True)
    sp.refresh_from_db()
    assert sp.image_source_type == ""


@pytest.mark.django_db
def test_species_admin_change_form_renders(client):
    User.objects.create_superuser(username="admin", password="pw", email="a@b.c")
    client.login(username="admin", password="pw")
    sp = Species.objects.create(name="Renderus testus", gbif_taxon_key=999099)
    resp = client.get(f"/admin/dashboard/species/{sp.pk}/change/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_species_admin_changelist_shows_lazy_thumbnail(client):
    User.objects.create_superuser(username="admin", password="pw", email="a@b.c")
    client.login(username="admin", password="pw")
    Species.objects.create(
        name="Thumbus testus",
        gbif_taxon_key=999100,
        image_url="https://example.org/thumb.jpg",
    )
    resp = client.get("/admin/dashboard/species/")
    assert resp.status_code == 200
    html = resp.content.decode()
    # The thumbnail is rendered lazily so the changelist stays light in the browser.
    assert 'src="https://example.org/thumb.jpg"' in html
    assert 'loading="lazy"' in html
    # A fixed box + object-fit:cover keeps the column uniform across aspect ratios.
    assert "object-fit:cover" in html
