"""Import-pipeline tests that drive run_import with in-memory rows.

Tests here do NOT use a DwCA zip file. Real-DwCA tests live in
test_import_observations.py (to be renamed to test_import_observations_dwca.py
once all logic tests are migrated).
"""

import pytest

from dashboard.models import (
    DataImport,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
)
from dashboard.tests.commands.factories import make_raw_row, run_import_with_rows

# iNaturalist gbif_dataset_key used by observations created in test_data
INATURALIST_KEY = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
# gbif_taxon_key values used by test_data (Lixus bardanae / Polydrusus planifrons)
LIXUS_KEY = 1224034
POLYDRUSUS_KEY = 7972617

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.sequential]


def test_run_import_with_rows_sanity():
    """One valid row in -> one Observation out. Confirms factories.py is
    wired correctly to run_import and the pipeline handles a trivial case."""
    Species.objects.all().delete()
    Species.objects.create(name="Lixus bardanae", gbif_taxon_key=LIXUS_KEY)

    run_import_with_rows([make_raw_row(gbif_id=42, occurrence_id="sanity-1")])

    assert Observation.objects.count() == 1
    obs = Observation.objects.get()
    assert obs.occurrence_id == "sanity-1"
    assert obs.gbif_id == "42"  # gbif_id is stored as a string on Observation


def test_initial_data_import_value_replaced(test_data):
    """When a new observation has the same stable_id as a pre-existing one,
    the new observation inherits the original's initial_data_import."""
    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=42,
                occurrence_id="https://www.inaturalist.org/observations/33366292",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=POLYDRUSUS_KEY,
                accepted_taxon_key=POLYDRUSUS_KEY,
                species_key=POLYDRUSUS_KEY,
            ),
        ]
    )

    observation_new_import = Observation.objects.get(
        occurrence_id="https://www.inaturalist.org/observations/33366292"
    )
    latest_di = DataImport.objects.latest("id")

    assert observation_new_import.initial_data_import == test_data["initial_di"]
    assert observation_new_import.data_import == latest_di


def test_initial_data_import_value_new(test_data):
    """A totally new occurrence's initial_data_import points to the current import."""
    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=99,
                occurrence_id="brand-new-occurrence",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_KEY,
                accepted_taxon_key=LIXUS_KEY,
                species_key=LIXUS_KEY,
            ),
        ]
    )

    obs = Observation.objects.get(occurrence_id="brand-new-occurrence")
    latest_di = DataImport.objects.latest("id")
    assert obs.initial_data_import == latest_di
    assert obs.data_import == latest_di


def test_dataimport_object_created(test_data):
    """Running run_import creates exactly one new DataImport object."""
    count_before = DataImport.objects.count()
    run_import_with_rows([make_raw_row(taxon_key=LIXUS_KEY)])
    assert DataImport.objects.count() == count_before + 1


def _row_replacing_unseen_observation(**overrides):
    """Build a row whose stable_id matches observation_unseen_to_be_replaced
    from test_data (inaturalist dataset, polydrusus, occurrence 33366292)."""
    defaults = dict(
        gbif_id=42,
        occurrence_id="https://www.inaturalist.org/observations/33366292",
        dataset_key=INATURALIST_KEY,
        dataset_name="iNaturalist",
        taxon_key=POLYDRUSUS_KEY,
        accepted_taxon_key=POLYDRUSUS_KEY,
        species_key=POLYDRUSUS_KEY,
    )
    return make_raw_row(**{**defaults, **overrides})


def test_observation_comments_migrated(test_data):
    """A comment on a replaced observation is re-linked to the new
    observation (same stable_id, different pk)."""
    comment = ObservationComment.objects.get()  # test_data creates exactly one
    previous_observation_id = comment.observation_id
    previous_stable_id = comment.observation.stable_id

    run_import_with_rows([_row_replacing_unseen_observation()])

    comment.refresh_from_db()
    assert comment.observation_id != previous_observation_id
    assert comment.observation.stable_id == previous_stable_id


def test_observation_unseen_migrated(test_data):
    """An ObservationUnseen is re-linked to the new observation when the
    old one is replaced; it stays unseen when the user's notification
    delay is long enough for the observation to still count as recent."""
    ou = test_data["observation_unseen_to_migrate"]
    previous_observation_id = ou.observation_id
    previous_stable_id = ou.observation.stable_id

    # Force a long delay so the new observation isn't auto-marked as seen
    # (otherwise the unseen gets deleted rather than migrated)
    user = test_data["user"]
    user.notification_delay_days = 365 * 20
    user.save()

    run_import_with_rows([_row_replacing_unseen_observation()])

    ou.refresh_from_db()
    assert ou.observation_id != previous_observation_id
    assert ou.observation.stable_id == previous_stable_id


def test_unmigrated_ou_gets_deleted(test_data):
    """An ObservationUnseen whose observation has no replacement in the
    new import is deleted along with that observation."""
    ou_id = test_data["observation_unseen_to_delete"].id

    # A row that does NOT match any pre-existing observation's stable_id;
    # the "observation_not_replaced" (occurrence_id='2') is simply absent
    # from this import, so its unseen row should be cleaned up.
    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=99,
                occurrence_id="brand-new-no-match",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_KEY,
                accepted_taxon_key=LIXUS_KEY,
                species_key=LIXUS_KEY,
            ),
        ]
    )

    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(id=ou_id)
