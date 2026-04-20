"""Shared fixtures for import_observations tests (DwCA and logic)."""

import datetime

import pytest
from django.contrib.gis.geos import Point
from django.db.models import QuerySet
from django.utils import timezone

from dashboard.models import (
    Alert,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
    User,
)


@pytest.fixture(autouse=True)
def use_static_files_storage(settings):
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def predicate_builder_belgium(species_list: QuerySet[Species]):
    """Build a GBIF.org download predicate for Belgian observations, after 2000.

    Species list is taken from the GBIF Alert database.
    """
    return {
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "COUNTRY", "value": "BE"},
                {
                    "type": "in",
                    "key": "TAXON_KEY",
                    "values": [f"{s.gbif_taxon_key}" for s in species_list],
                },
                {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "present"},
                {
                    "type": "greaterThanOrEquals",
                    "key": "YEAR",
                    "value": 2010,
                },
            ],
        }
    }


@pytest.fixture
def test_data():
    """Create all shared test objects used by most import test functions."""
    user = User.objects.create_user(
        username="testuser",
        password="12345",
        first_name="John",
        last_name="Frusciante",
        email="frusciante@gmail.com",
        notification_delay_days=365,
    )

    Species.objects.all().delete()  # There are initially a few species in the database (loaded in data migration)
    lixus = Species.objects.create(name="Lixus bardanae", gbif_taxon_key=1224034)
    polydrusus = Species.objects.create(
        name="Polydrusus planifrons", gbif_taxon_key=7972617
    )

    inaturalist = Dataset.objects.create(
        name="iNaturalist", gbif_dataset_key="50c9509d-22c7-4a22-a47d-8c48425ef4a7"
    )

    dataset_without_observations = Dataset.objects.create(
        name="Dataset without observations",
        gbif_dataset_key="50c9509d-22c7-4a22-a47d-8c48425ef4a8",
    )

    alert_referencing_unused_dataset = Alert.objects.create(
        name="Alert referencing unused dataset",
        user=user,
    )
    alert_referencing_unused_dataset.datasets.add(
        dataset_without_observations, inaturalist
    )
    alert_referencing_unused_dataset.species.add(lixus)

    # We need this one to make sure the observation is automatically marked as seen
    # in test_observation_unseen_migrated()
    alert_referencing_obs_unseen_to_be_replaced = Alert.objects.create(
        name="Alert referencing observation unseen to be replaced",
        user=user,
    )
    alert_referencing_obs_unseen_to_be_replaced.species.add(polydrusus)

    # This observation will be replaced during the import process
    # because there's a row with the same occurrence_id and dataset_key in the DwC-A
    initial_di = DataImport.objects.create(start=timezone.now())
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    observation_unseen_to_be_replaced = Observation.objects.create(
        gbif_id=1,
        occurrence_id="https://www.inaturalist.org/observations/33366292",
        source_dataset=inaturalist,
        species=polydrusus,
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=initial_di,
        initial_data_import=initial_di,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )

    observation_seen_to_be_replaced = Observation.objects.create(
        gbif_id=3,
        occurrence_id="https://www.inaturalist.org/observations/42577016",
        source_dataset=inaturalist,
        species=polydrusus,
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=initial_di,
        initial_data_import=initial_di,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )

    # This one has no equivalent in the DwC-A
    observation_not_replaced = Observation.objects.create(
        gbif_id=2,
        occurrence_id="2",
        source_dataset=inaturalist,
        species=lixus,
        date=datetime.date.today(),
        data_import=initial_di,
        initial_data_import=initial_di,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )

    ObservationComment.objects.create(
        author=user,
        observation=observation_unseen_to_be_replaced,
        text="This is a comment to migrate",
    )

    observation_unseen_to_migrate = ObservationUnseen.objects.create(
        user=user, observation=observation_unseen_to_be_replaced
    )

    # We also create this one, so we can check it gets deleted in the new import
    # process, and that it doesn't prevent the related observation to be deleted
    observation_unseen_to_delete = ObservationUnseen.objects.create(
        user=user, observation=observation_not_replaced
    )

    return {
        "user": user,
        "lixus": lixus,
        "polydrusus": polydrusus,
        "initial_di": initial_di,
        "inaturalist": inaturalist,
        "dataset_without_observations": dataset_without_observations,
        "alert_referencing_unused_dataset": alert_referencing_unused_dataset,
        "observation_unseen_to_be_replaced": observation_unseen_to_be_replaced,
        "observation_seen_to_be_replaced": observation_seen_to_be_replaced,
        "observation_unseen_to_migrate": observation_unseen_to_migrate,
        "observation_unseen_to_delete": observation_unseen_to_delete,
    }


@pytest.fixture
def gbif_download_config(settings):
    """Override GBIF_ALERT settings with test GBIF download config."""
    settings.GBIF_ALERT = {
        "GBIF_DOWNLOAD_CONFIG": {
            "PREDICATE_BUILDER": predicate_builder_belgium,
            "USERNAME": "riparias-dev",
            "PASSWORD": "riparias-dev",
        },
    }
