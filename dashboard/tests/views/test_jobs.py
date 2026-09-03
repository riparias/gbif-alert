import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import (
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationUnseen,
    Species,
)
from dashboard.views.jobs import mark_many_observations_as_seen

pytestmark = pytest.mark.django_db


@pytest.fixture
def unseen_data():
    """Five observations of one species and one of another, all unseen by
    `user`; the first one is also unseen by `other_user`."""
    User = get_user_model()
    user = User.objects.create_user(username="u", email="u@example.org", password="p")
    other_user = User.objects.create_user(
        username="o", email="o@example.org", password="p"
    )
    di = DataImport.objects.create(start=timezone.now())
    dataset = Dataset.objects.create(name="D", gbif_dataset_key="k")
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=1)
    other_species = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2)

    observations = [
        Observation.objects.create(
            gbif_id=i,
            occurrence_id=str(i),
            species=species if i < 5 else other_species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=dataset,
            location=Point(4.35, 50.65, srid=4326),
            basis_of_record=basis,
        )
        for i in range(6)
    ]
    for obs in observations:
        ObservationUnseen.objects.create(observation=obs, user=user)
    ObservationUnseen.objects.create(observation=observations[0], user=other_user)
    return {
        "user": user,
        "other_user": other_user,
        "species": species,
        "observations": observations,
    }


def test_mark_many_as_seen_deletes_only_this_users_matching_unseen_rows(unseen_data):
    user = unseen_data["user"]
    matching = Observation.objects.filter(species=unseen_data["species"])

    mark_many_observations_as_seen(matching, user)

    assert not ObservationUnseen.objects.filter(
        user=user, observation__in=matching
    ).exists()
    # The non-matching observation stays unseen for this user...
    assert ObservationUnseen.objects.filter(
        user=user, observation=unseen_data["observations"][5]
    ).exists()
    # ...and the other user's row is untouched.
    assert ObservationUnseen.objects.filter(user=unseen_data["other_user"]).count() == 1


def test_mark_many_as_seen_runs_a_bounded_number_of_queries(
    unseen_data, django_assert_max_num_queries
):
    """One DELETE per observation kept the database busy for minutes on a
    150k-observation alert, right when the user goes back to browsing it."""
    matching = Observation.objects.filter(species=unseen_data["species"])

    with django_assert_max_num_queries(2):
        mark_many_observations_as_seen(matching, unseen_data["user"])
