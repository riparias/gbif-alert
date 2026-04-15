import datetime

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import (
    BasisOfRecord,
    Dataset,
    DataImport,
    Observation,
    ObservationComment,
    Species,
    User,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()

pytestmark = pytest.mark.django_db


@pytest.fixture
def comment_data():
    jason = User.objects.create_user(
        username="jasonlytle",
        password="am180",
        first_name="Jason",
        last_name="Lytle",
        email="jason@grandaddy.com",
    )
    di = DataImport.objects.create(start=timezone.now())
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    observation = Observation.objects.create(
        gbif_id=1,
        occurrence_id="1",
        species=Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526),
        date=SEPTEMBER_13_2021,
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(
            name="Test dataset",
            gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        ),
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    jasons_comment = ObservationComment.objects.create(
        observation=observation,
        author=jason,
        text="I love this observation!",
    )
    return {"jason": jason, "jasons_comment": jasons_comment}


def test_comment_can_be_emptied(comment_data):
    """A comment can be emptied via the make_empty() method."""
    jason = comment_data["jason"]
    jasons_comment = comment_data["jasons_comment"]

    assert jasons_comment.author == jason
    assert jasons_comment.text == "I love this observation!"
    assert not jasons_comment.emptied_because_author_deleted_account

    jasons_comment.make_empty()

    jasons_comment.refresh_from_db()
    assert jasons_comment.author is None
    assert jasons_comment.text == ""
    assert jasons_comment.emptied_because_author_deleted_account
