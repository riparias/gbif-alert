import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon

from dashboard.models import Alert, AlertTemplate, Area, Species


@pytest.fixture()
def promote_data():
    User = get_user_model()
    operator = User.objects.create_user(username="op", password="x", email="op@e.com")
    sp1 = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    sp2 = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
    area = Area.objects.create(
        name="Region X",
        mpoly=MultiPolygon(
            Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
            srid=4326,
        ),
    )
    alert = Alert.objects.create(
        name="Amphibians near X", user=operator,
        email_notifications_frequency="W",
        area_filter_mode=Alert.AREA_FILTER_APPROACHING,
        approaching_distance_km=50,
        verified_filter=Alert.VERIFIED_FILTER_VERIFIED_ONLY,
    )
    alert.species.set([sp1, sp2])
    alert.areas.set([area])
    return {"operator": operator, "alert": alert, "sp1": sp1, "sp2": sp2, "area": area}


@pytest.mark.django_db
def test_create_from_alert_snapshots_scalar_and_m2m(promote_data):
    alert = promote_data["alert"]
    tpl = AlertTemplate.create_from_alert(alert, created_by=promote_data["operator"])

    assert tpl.pk is not None
    assert tpl.created_by == promote_data["operator"]
    # scalar filter fields copied
    assert tpl.area_filter_mode == Alert.AREA_FILTER_APPROACHING
    assert tpl.approaching_distance_km == 50
    assert tpl.verified_filter == Alert.VERIFIED_FILTER_VERIFIED_ONLY
    # M2M copied
    assert set(tpl.species.all()) == {promote_data["sp1"], promote_data["sp2"]}
    assert set(tpl.areas.all()) == {promote_data["area"]}
    # name seeded from the alert name (current language)
    assert tpl.name == "Amphibians near X"


@pytest.mark.django_db
def test_template_is_not_an_alert_row(promote_data):
    """Templates must never appear in Alert.objects (notification isolation)."""
    AlertTemplate.create_from_alert(promote_data["alert"], created_by=promote_data["operator"])
    assert Alert.objects.count() == 1  # only the operator's own alert


@pytest.mark.django_db
def test_deleting_template_nulls_alert_pointer(promote_data):
    tpl = AlertTemplate.create_from_alert(promote_data["alert"], created_by=promote_data["operator"])
    a = Alert.objects.create(name="copy", user=promote_data["operator"], created_from_template=tpl)
    tpl.delete()
    a.refresh_from_db()
    assert a.created_from_template is None
    assert Alert.objects.filter(pk=a.pk).exists()
