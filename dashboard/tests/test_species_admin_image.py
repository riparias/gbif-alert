import pytest
from django.contrib.admin.sites import AdminSite
from dashboard.admin import SpeciesAdmin
from dashboard.models import Species


class _Form:
    def __init__(self, changed):
        self.changed_data = changed


@pytest.mark.django_db
def test_admin_manual_url_sets_provenance_manual():
    sp = Species(name="Testus specius", gbif_taxon_key=999020,
                 image_url="https://example.org/x.jpg")
    admin = SpeciesAdmin(Species, AdminSite())
    admin.save_model(request=None, obj=sp, form=_Form(["image_url"]), change=False)
    assert sp.image_source_type == "manual"


@pytest.mark.django_db
def test_admin_clearing_url_resets_provenance():
    sp = Species(name="Testus specius", gbif_taxon_key=999021,
                 image_url="", image_source_type="wikipedia")
    admin = SpeciesAdmin(Species, AdminSite())
    admin.save_model(request=None, obj=sp, form=_Form(["image_url"]), change=True)
    assert sp.image_source_type == ""


@pytest.mark.django_db
def test_species_admin_change_form_renders(client):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    User.objects.create_superuser(username="admin", password="pw", email="a@b.c")
    client.login(username="admin", password="pw")
    sp = Species.objects.create(name="Renderus testus", gbif_taxon_key=999099)
    resp = client.get(f"/admin/dashboard/species/{sp.pk}/change/")
    assert resp.status_code == 200
