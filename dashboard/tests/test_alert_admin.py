import datetime
from unittest import mock

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import (
    Alert,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationUnseen,
    Species,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def alert_with_one_unseen(django_user_model):
    """An alert whose owner has exactly one unseen matching observation."""
    user = django_user_model.objects.create_user("owner", "owner@e.com", "pw")
    species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    di = DataImport.objects.create(start=timezone.now())
    observation = Observation.objects.create(
        gbif_id=1,
        occurrence_id="1",
        species=species,
        date=datetime.date(2021, 9, 13),
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        ),
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=BasisOfRecord.objects.create(name="HUMAN_OBSERVATION"),
    )
    ObservationUnseen.objects.create(observation=observation, user=user)
    alert = Alert.objects.create(user=user, name="My alert")
    alert.species.add(species)
    return alert


@pytest.fixture
def admin_client_logged(client, django_user_model):
    admin = django_user_model.objects.create_superuser("adm", "adm@e.com", "pw")
    client.force_login(admin)
    return client


def test_alert_changelist_does_not_count_unseen_observations(
    admin_client_logged, alert_with_one_unseen
):
    """The alerts list must not compute the unseen count for each row.

    That count is a full spatial query per alert (up to seconds each), so
    showing it for every row made /admin/dashboard/alert/ time out in
    production. Guards against the column being added back.
    """
    with mock.patch.object(
        Alert, "unseen_observations_count", new_callable=mock.PropertyMock
    ) as count:
        resp = admin_client_logged.get("/admin/dashboard/alert/")
    assert resp.status_code == 200
    assert "My alert" in resp.content.decode()
    count.assert_not_called()


def test_alert_change_page_shows_unseen_observations_count(
    admin_client_logged, alert_with_one_unseen
):
    """The unseen count moved from the list to the alert's own admin page, so
    admins can still see it, one alert at a time."""
    resp = admin_client_logged.get(
        f"/admin/dashboard/alert/{alert_with_one_unseen.pk}/change/"
    )
    assert resp.status_code == 200
    assert '<div class="readonly">1</div>' in resp.content.decode()


def test_alert_add_page_renders_without_unseen_count(admin_client_logged):
    """On the add page the alert is unsaved, so the count can't be computed
    (its M2M relations raise ValueError). The page must still render rather
    than crash on the read-only field."""
    resp = admin_client_logged.get("/admin/dashboard/alert/add/")
    assert resp.status_code == 200
