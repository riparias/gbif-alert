import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import ValidationError

from dashboard.models import Area


def _mpoly():
    return MultiPolygon(
        Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
        srid=4326,
    )


@pytest.mark.django_db
def test_default_home_filter_defaults_to_false():
    area = Area.objects.create(name="Region X", mpoly=_mpoly())
    assert area.is_default_home_filter is False


@pytest.mark.django_db
def test_default_home_filter_allowed_on_public_area():
    area = Area(name="Region X", mpoly=_mpoly(), is_default_home_filter=True)
    area.full_clean()  # does not raise


@pytest.mark.django_db
def test_default_home_filter_rejected_on_user_specific_area():
    user = get_user_model().objects.create_user(
        username="frusciante", password="12345", email="frusciante@gmail.com"
    )
    area = Area(
        name="My secret garden",
        mpoly=_mpoly(),
        owner=user,
        is_default_home_filter=True,
    )

    with pytest.raises(ValidationError) as excinfo:
        area.full_clean()

    assert "is_default_home_filter" in excinfo.value.message_dict
