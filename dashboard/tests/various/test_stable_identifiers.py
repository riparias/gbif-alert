import datetime

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from dashboard.models import BasisOfRecord, DataImport, Dataset, Observation, Species

SAMPLE_DATASET_KEY = "940821c0-3269-11df-855a-b8a03c50a862"
SAMPLE_OCCURRENCE_ID = "BR:IFBL: 00494798"
EXPECTED_STABLE_ID = "e58dabf7bcc72dc6b3e057859ed89a453eea527d"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_static_files_storage(settings):
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


@pytest.fixture
def obs_and_species():
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    species_p_fallax = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    di = DataImport.objects.create(start=timezone.now())
    obs = Observation.objects.create(
        gbif_id=1,
        occurrence_id=SAMPLE_OCCURRENCE_ID,
        species=species_p_fallax,
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=di,
        initial_data_import=di,
        source_dataset=Dataset.objects.create(
            name="Test dataset", gbif_dataset_key=SAMPLE_DATASET_KEY
        ),
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    return {"obs": obs, "species_p_fallax": species_p_fallax}


def test_stable_correct_value(obs_and_species):
    """The stable identifier has the expected value."""
    assert obs_and_species["obs"].stable_id == EXPECTED_STABLE_ID


def test_follows_occurrence_id(obs_and_species):
    """The stable identifier changes if the occurrence_id is updated."""
    obs = obs_and_species["obs"]
    stable_id_before = obs.stable_id
    obs.occurrence_id = "something new"
    obs.save()
    obs.refresh_from_db()
    assert obs.stable_id != stable_id_before


def test_follows_dataset_key(obs_and_species):
    """The stable identifier changes if the dataset key is updated."""
    obs = obs_and_species["obs"]
    stable_id_before = obs.stable_id
    obs.source_dataset.gbif_dataset_key = "something new"
    obs.source_dataset.save()
    obs.refresh_from_db()
    assert obs.stable_id != stable_id_before


def test_follows_dataset_change(obs_and_species):
    """The stable identifier changes if the observation gets linked to another dataset."""
    obs = obs_and_species["obs"]
    stable_id_before = obs.stable_id
    obs.source_dataset = Dataset.objects.create(name="New dataset", gbif_dataset_key="newdatasetid")
    obs.save()
    obs.refresh_from_db()
    assert obs.stable_id != stable_id_before


def test_dont_follow_unrelated_fields(obs_and_species):
    """Updating unrelated fields does not change the stable identifier."""
    obs = obs_and_species["obs"]
    stable_id_before = obs.stable_id
    obs.species = obs_and_species["species_p_fallax"]
    obs.date = datetime.date.today()
    obs.data_import = DataImport.objects.create(start=timezone.now())
    obs.source_dataset.name = "Renamed dataset"
    obs.source_dataset.save()
    obs.save()
    assert obs.stable_id == stable_id_before
