"""Django admin changelists that are known to be query-sensitive."""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from dashboard.models import BasisOfRecord, DataImport, Dataset, Observation, Species

pytestmark = pytest.mark.django_db


def _make_observations(n: int) -> None:
    """n observations, each with its own species and dataset, so a changelist
    that fetches those per row issues 2n extra queries."""
    basis = BasisOfRecord.objects.create(name=f"BOR-{n}")
    di = DataImport.objects.create(start=timezone.now())
    for i in range(n):
        Observation.objects.create(
            gbif_id=80000 + n * 100 + i,
            occurrence_id=f"admin-{n}-{i}",
            species=Species.objects.create(
                name=f"Sp {n}-{i}", gbif_taxon_key=90000 + n * 100 + i
            ),
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name=f"Ds {n}-{i}", gbif_dataset_key=f"ds-{n}-{i}"
            ),
            location=Point(4.35, 50.85, srid=4326),
            basis_of_record=basis,
        )


def _changelist_query_count(client, n: int) -> int:
    Observation.objects.all().delete()
    _make_observations(n)
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(reverse("admin:dashboard_observation_changelist"))
    assert response.status_code == 200
    return len(ctx.captured_queries)


def test_observation_changelist_query_count_does_not_grow_with_rows(client):
    """species and source_dataset are list_display columns: without
    list_select_related the changelist runs two queries per row."""
    client.force_login(
        get_user_model().objects.create_superuser("root", "root@example.com", "pw")
    )
    assert _changelist_query_count(client, 20) == _changelist_query_count(client, 3)
