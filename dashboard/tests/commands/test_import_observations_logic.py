"""Import-pipeline tests that drive run_import with in-memory rows.

Tests here do NOT use a DwCA zip file. Real-DwCA tests live in
test_import_observations_dwca.py.
"""

import datetime
from unittest import mock

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from maintenance_mode.core import (  # type: ignore
    get_maintenance_mode,
    set_maintenance_mode,
)

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
from dashboard.tests.commands.factories import make_raw_row, run_import_with_rows

# iNaturalist gbif_dataset_key used by observations created in test_data
INATURALIST_KEY = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
# Legacy (frozen) GBIF backbone gbif_taxon_key values used by test_data
LIXUS_KEY = 1224034
POLYDRUSUS_KEY = 7972617
# The real COL XR keys those taxa map to - alphanumeric, as returned by the GBIF
# v2 match API and as they appear in a COL XR download's taxonKey columns.
LIXUS_COL_KEY = "3VPFV"  # Lixus bardanae
POLYDRUSUS_COL_KEY = "4L6VJ"  # Polydrusus planifrons

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.sequential]


def test_zero_rows_import(test_data):
    """run_import handles an empty row stream gracefully: a DataImport is
    still created (counters at 0), all previous observations are deleted,
    and the transaction commits normally."""
    obs_ids_before = set(Observation.objects.values_list("id", flat=True))
    di_count_before = DataImport.objects.count()
    assert obs_ids_before  # sanity: test_data creates some observations

    run_import_with_rows([])

    assert DataImport.objects.count() == di_count_before + 1
    di = DataImport.objects.latest("id")
    assert di.completed
    assert di.end is not None
    assert di.imported_observations_counter == 0
    assert di.skipped_observations_counter == 0

    # Previous-import observations are gone, same as any other import
    obs_ids_after = set(Observation.objects.values_list("id", flat=True))
    assert not (obs_ids_before & obs_ids_after)
    assert obs_ids_after == set()


def test_maintenance_mode_cleared_after_success(test_data):
    """On a successful import run_import leaves maintenance mode OFF.

    Companion to test_transaction and
    test_failed_import_clears_maintenance_and_emails_admins, which assert the
    other half of the contract: maintenance mode is also cleared when the
    import raises (the transaction rolls back, so nothing needs guarding).
    """
    # Baseline: some prior test could have left it on. Clear it first.
    set_maintenance_mode(False)
    assert get_maintenance_mode() is False

    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=1,
                occurrence_id="mm-check",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    assert get_maintenance_mode() is False


def test_run_import_with_rows_sanity():
    """One valid row in -> one Observation out. Confirms factories.py is
    wired correctly to run_import and the pipeline handles a trivial case."""
    Species.objects.all().delete()
    Species.objects.create(
        name="Lixus bardanae",
        gbif_taxon_key=LIXUS_KEY,
        gbif_col_taxon_key=LIXUS_COL_KEY,
    )

    run_import_with_rows([make_raw_row(gbif_id=42, occurrence_id="sanity-1")])

    assert Observation.objects.count() == 1
    obs = Observation.objects.get()
    assert obs.occurrence_id == "sanity-1"
    assert obs.gbif_id == "42"  # gbif_id is stored as a string on Observation


def test_verified_classification(test_data):
    """build_observation_from_raw maps identification_verification_status to
    obs.verified via verification_status_classification.json:

    - a key marked verified=true   -> obs.verified is True
    - a key marked verified=false  -> obs.verified is False
    - an unknown string            -> fallback to False (dict.get default)
    - empty string                 -> also False (it's an explicit entry)

    The raw status string itself is preserved on the observation (no
    mapping / normalization), so alerting / filtering code downstream
    can inspect it independently of the boolean.
    """
    rows = [
        make_raw_row(
            gbif_id=1,
            occurrence_id="verified-yes",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            identification_verification_status="validated",
        ),
        make_raw_row(
            gbif_id=2,
            occurrence_id="verified-no",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            identification_verification_status="Unvalidated",
        ),
        make_raw_row(
            gbif_id=3,
            occurrence_id="verified-unknown",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            identification_verification_status="not-a-known-classification",
        ),
        make_raw_row(
            gbif_id=4,
            occurrence_id="verified-empty",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            # default is "" which is explicitly in the JSON as verified=false
        ),
    ]

    run_import_with_rows(rows)

    yes = Observation.objects.get(occurrence_id="verified-yes")
    no = Observation.objects.get(occurrence_id="verified-no")
    unknown = Observation.objects.get(occurrence_id="verified-unknown")
    empty = Observation.objects.get(occurrence_id="verified-empty")

    assert yes.verified is True
    assert no.verified is False
    assert unknown.verified is False
    assert empty.verified is False

    # Raw status string is preserved verbatim on the observation
    assert yes.identification_verification_status == "validated"
    assert no.identification_verification_status == "Unvalidated"
    assert unknown.identification_verification_status == "not-a-known-classification"
    assert empty.identification_verification_status == ""


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
                taxon_key=POLYDRUSUS_COL_KEY,
                accepted_taxon_key=POLYDRUSUS_COL_KEY,
                species_key=POLYDRUSUS_COL_KEY,
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
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    obs = Observation.objects.get(occurrence_id="brand-new-occurrence")
    latest_di = DataImport.objects.latest("id")
    assert obs.initial_data_import == latest_di
    assert obs.data_import == latest_di


def test_duplicate_stable_id_within_one_import_is_rejected(test_data, monkeypatch):
    """Two rows in one archive sharing occurrence_id + dataset_key are refused.

    The second row lands in a later chunk, so the chunk lookup finds the first
    one already inserted under the *current* import. That is not older than the
    row being built, so the import raises instead of silently keeping one of
    the two.

    Covers the OtherIdenticalObservationIsNewer branch of
    _set_initial_data_import, which the chunk-batched lookup reimplemented.
    """
    from dashboard.management.commands import import_observations as mod

    monkeypatch.setattr(mod, "BULK_CREATE_CHUNK_SIZE", 1)

    duplicated = dict(
        occurrence_id="same-occurrence-appearing-twice",
        dataset_key=INATURALIST_KEY,
        dataset_name="iNaturalist",
        taxon_key=LIXUS_COL_KEY,
        accepted_taxon_key=LIXUS_COL_KEY,
        species_key=LIXUS_COL_KEY,
    )

    with pytest.raises(Observation.OtherIdenticalObservationIsNewer):
        run_import_with_rows(
            [
                make_raw_row(gbif_id=8001, **duplicated),
                make_raw_row(gbif_id=8002, **duplicated),
            ]
        )


def test_two_stored_observations_sharing_a_stable_id_are_rejected(test_data):
    """Two stored observations with the same stable_id make the import refuse.

    The unique constraint is on (stable_id, data_import), so an interrupted
    earlier import can leave two rows sharing a stable_id. Which one to inherit
    initial_data_import from is undefined, so the import raises rather than
    picking arbitrarily.

    Covers the MultipleObjectsReturned branch of _set_initial_data_import.
    """
    occurrence_id = "https://www.inaturalist.org/observations/33366292"
    # test_data already stores one observation with this occurrence_id, under
    # its own DataImport. Add a second one under a different DataImport so two
    # stored rows share a stable_id.
    other_di = DataImport.objects.create(start=timezone.now())
    Observation.objects.create(
        gbif_id=7001,
        occurrence_id=occurrence_id,
        source_dataset=test_data["inaturalist"],
        species=test_data["polydrusus"],
        date=datetime.date.today() - datetime.timedelta(days=1),
        data_import=other_di,
        initial_data_import=other_di,
        location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=BasisOfRecord.objects.get(name="HUMAN_OBSERVATION"),
    )

    with pytest.raises(Observation.MultipleObjectsReturned):
        run_import_with_rows(
            [
                make_raw_row(
                    gbif_id=7002,
                    occurrence_id=occurrence_id,
                    dataset_key=INATURALIST_KEY,
                    dataset_name="iNaturalist",
                    taxon_key=POLYDRUSUS_COL_KEY,
                    accepted_taxon_key=POLYDRUSUS_COL_KEY,
                    species_key=POLYDRUSUS_COL_KEY,
                ),
            ]
        )


def test_dataimport_object_created(test_data):
    """Running run_import creates exactly one new DataImport object."""
    count_before = DataImport.objects.count()
    run_import_with_rows([make_raw_row(taxon_key=LIXUS_COL_KEY)])
    assert DataImport.objects.count() == count_before + 1


def _row_replacing_unseen_observation(**overrides):
    """Build a row whose stable_id matches observation_unseen_to_be_replaced
    from test_data (inaturalist dataset, polydrusus, occurrence 33366292)."""
    defaults = dict(
        gbif_id=42,
        occurrence_id="https://www.inaturalist.org/observations/33366292",
        dataset_key=INATURALIST_KEY,
        dataset_name="iNaturalist",
        taxon_key=POLYDRUSUS_COL_KEY,
        accepted_taxon_key=POLYDRUSUS_COL_KEY,
        species_key=POLYDRUSUS_COL_KEY,
    )
    return make_raw_row(**{**defaults, **overrides})


def _row_replacing_seen_observation(**overrides):
    """Build a row whose stable_id matches observation_seen_to_be_replaced
    from test_data (inaturalist dataset, polydrusus, occurrence 42577016)."""
    defaults = dict(
        gbif_id=55,
        occurrence_id="https://www.inaturalist.org/observations/42577016",
        dataset_key=INATURALIST_KEY,
        dataset_name="iNaturalist",
        taxon_key=POLYDRUSUS_COL_KEY,
        accepted_taxon_key=POLYDRUSUS_COL_KEY,
        species_key=POLYDRUSUS_COL_KEY,
    )
    return make_raw_row(**{**defaults, **overrides})


def test_ignore_unusable_observations_logic(test_data):
    """Each skip rule in build_observation_from_raw skips its row.

    Complements the DwCA-backed test_ignore_unusable_observations (which
    verifies the same logic end-to-end through the real DwCA format).
    """
    good_row = make_raw_row(
        gbif_id=1,
        occurrence_id="good-1",
        dataset_key=INATURALIST_KEY,
        dataset_name="iNaturalist",
        taxon_key=LIXUS_COL_KEY,
        accepted_taxon_key=LIXUS_COL_KEY,
        species_key=LIXUS_COL_KEY,
    )
    rows = [
        good_row,
        # missing longitude -> skip
        make_raw_row(
            gbif_id=2,
            occurrence_id="no-lon",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            decimal_longitude=None,
        ),
        # missing latitude -> skip
        make_raw_row(
            gbif_id=3,
            occurrence_id="no-lat",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            decimal_latitude=None,
        ),
        # missing year -> skip
        make_raw_row(
            gbif_id=4,
            occurrence_id="no-year",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            year=None,
        ),
        # empty occurrence_id -> skip
        make_raw_row(
            gbif_id=5,
            occurrence_id="",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
        # absence (occurrence_status != "PRESENT") -> skip
        make_raw_row(
            gbif_id=6,
            occurrence_id="absent-1",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
            occurrence_status="ABSENT",
        ),
    ]

    run_import_with_rows(rows)

    assert Observation.objects.count() == 1
    assert Observation.objects.get().occurrence_id == "good-1"
    assert DataImport.objects.latest("id").skipped_observations_counter == 5


def _recent_raw_row(**overrides):
    """make_raw_row with a date 30 days before today - guaranteed within
    any reasonable notification_delay_days (default 365)."""
    d = datetime.date.today() - datetime.timedelta(days=30)
    return make_raw_row(year=d.year, month=d.month, day=d.day, **overrides)


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


def test_comment_on_unreplaced_observation_is_cascade_deleted(test_data):
    """A comment on an observation that has NO replacement in the new
    import is cascade-deleted along with its observation.

    Documents current behavior, worth pinning before the perf refactor:
    ObservationComment.observation is on_delete=CASCADE, and run_import
    wipes old-import observations with a bulk ``exclude().delete()``.
    The comment-migration code in _batch_insert_observations only re-
    links comments for observations whose stable_id DOES match a new
    row; comments on orphaned observations are silently lost.
    """
    # Attach a second comment to an observation that will NOT be
    # replaced by this import (observation_not_replaced, reachable via
    # observation_unseen_to_delete.observation - it's created in test_data
    # but not exposed directly).
    # test_data already puts one comment on observation_unseen_to_be_replaced,
    # which WILL be replaced here.
    orphaned_observation = test_data["observation_unseen_to_delete"].observation
    ObservationComment.objects.create(
        author=test_data["user"],
        observation=orphaned_observation,
        text="this comment should vanish",
    )
    assert ObservationComment.objects.count() == 2  # sanity

    # Import only replaces observation_unseen_to_be_replaced.
    run_import_with_rows([_row_replacing_unseen_observation()])

    # The migrated comment survives on the replacement; the orphan is gone.
    surviving_comments = list(ObservationComment.objects.all())
    assert len(surviving_comments) == 1
    assert surviving_comments[0].text == "This is a comment to migrate"


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


def test_multi_user_unseen_migration_with_different_delays(test_data):
    """migrate_unseen_observations decides delete-vs-migrate INDEPENDENTLY
    per ObservationUnseen, using that unseen's own user.notification_delay_days.

    Scenario: the same pre-existing observation is unseen by two extra
    users, A (short delay, 30 days) and B (very long delay, 20 years).
    A row in the new import replaces that observation with a date years
    in the past (default make_raw_row date).

    Expected: A's unseen is deleted (too old for 30-day delay); B's
    unseen is migrated to the new observation (still "recent" for a
    20-year delay).
    """
    user_strict = User.objects.create_user(
        username="strict_user",
        password="pw",
        email="strict@example.com",
        notification_delay_days=30,
    )
    user_lenient = User.objects.create_user(
        username="lenient_user",
        password="pw",
        email="lenient@example.com",
        notification_delay_days=365 * 20,
    )
    existing_obs = test_data["observation_unseen_to_be_replaced"]
    strict_unseen = ObservationUnseen.objects.create(
        user=user_strict, observation=existing_obs
    )
    lenient_unseen = ObservationUnseen.objects.create(
        user=user_lenient, observation=existing_obs
    )

    # Default row date is years old: too old for 30 days, still recent
    # for 20 years.
    run_import_with_rows([_row_replacing_unseen_observation()])

    new_obs = Observation.objects.get(occurrence_id=existing_obs.occurrence_id)

    # Strict user: unseen deleted (replacement is older than delay)
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(id=strict_unseen.id)

    # Lenient user: unseen migrated to the new observation
    lenient_unseen.refresh_from_db()
    assert lenient_unseen.observation == new_obs


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
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(id=ou_id)


def test_old_observations_deleted(test_data):
    """Observations from previous imports are gone after a new import."""
    ids_before = set(Observation.objects.values_list("id", flat=True))

    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=999,
                occurrence_id="any-new-occurrence",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    ids_after = set(Observation.objects.values_list("id", flat=True))
    assert not (ids_before & ids_after)


def test_seen_status_unseen_to_seen_age(test_data):
    """An ObservationUnseen linked to an observation whose replacement is
    older than the user's notification delay gets deleted (new obs treated
    as seen). Default user delay is 365 days; default row date is years
    old, so it qualifies as 'too old'."""
    run_import_with_rows([_row_replacing_unseen_observation()])

    obs = Observation.objects.get(
        occurrence_id=test_data["observation_unseen_to_be_replaced"].occurrence_id
    )
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs, user=test_data["user"])


def test_seen_status_unseen_to_unseen(test_data):
    """Same replacement scenario but with a very long user delay: the new
    observation still counts as recent, so the unseen is re-linked rather
    than deleted."""
    user = test_data["user"]
    user.notification_delay_days = 365 * 20
    user.save()

    run_import_with_rows([_row_replacing_unseen_observation()])

    obs = Observation.objects.get(
        occurrence_id=test_data["observation_unseen_to_be_replaced"].occurrence_id
    )
    # Should not raise - the unseen was migrated to the replacement
    ObservationUnseen.objects.get(observation=obs, user=user)


def test_seen_status_seen_to_seen(test_data):
    """An observation with no prior ObservationUnseen stays without one
    after being replaced."""
    run_import_with_rows([_row_replacing_seen_observation()])

    obs = Observation.objects.get(
        occurrence_id=test_data["observation_seen_to_be_replaced"].occurrence_id
    )
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs, user=test_data["user"])


def test_seen_status_new_to_seen_because_no_alert(test_data):
    """A brand-new, recent observation is NOT marked unseen when the user
    has no alert matching it."""
    Alert.objects.filter(user=test_data["user"]).delete()

    run_import_with_rows(
        [
            _recent_raw_row(
                gbif_id=77,
                occurrence_id="totally-new",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    obs = Observation.objects.get(occurrence_id="totally-new")
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs, user=test_data["user"])


def test_seen_status_new_to_seen_because_old(test_data):
    """A brand-new observation older than the user's delay is NOT marked
    unseen, even when an alert matches its species."""
    alert = Alert.objects.create(
        user=test_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(test_data["lixus"])

    # Default date on make_raw_row is years old - older than 365-day delay
    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=88,
                occurrence_id="old-lixus",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    obs = Observation.objects.get(occurrence_id="old-lixus")
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs, user=test_data["user"])


def test_seen_status_new_to_unseen(test_data):
    """A brand-new, recent observation that matches a user's alert by
    species gets an ObservationUnseen record."""
    alert = Alert.objects.create(
        user=test_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(test_data["lixus"])

    run_import_with_rows(
        [
            _recent_raw_row(
                gbif_id=99,
                occurrence_id="recent-lixus",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    obs = Observation.objects.get(occurrence_id="recent-lixus")
    # Should not raise - unseen was created
    ObservationUnseen.objects.get(observation=obs, user=test_data["user"])


def test_chunked_import_detects_replacement_in_later_chunk(test_data, monkeypatch):
    """With BULK_CREATE_CHUNK_SIZE overridden small, the import flushes
    to the DB in multiple batches. Verify that:

    - _batch_insert_observations is actually called more than once
    - all rows are imported (nothing lost at chunk boundaries)
    - replacement detection (stable_id lookup against pre-existing DB
      rows) works for a row that lands in a later chunk
    - the comment on the replaced observation ends up on the new row
      inserted in the later chunk

    Chunking (pinned here so a refactor does not silently change it): rows are
    pulled from the source a chunk at a time, so with CHUNK_SIZE=3 and 7 rows
    the flushes carry 3, 3 and 1 items - three in total.

    This replaced an earlier off-by-one: the flush used to fire when ``index >
    0 and index % CHUNK_SIZE == 0``, which made the first batch carry
    CHUNK_SIZE + 1 items and dropped the final flush whenever the row count was
    an exact multiple. That shape was itself pinned by this test, which is what
    forced the change to be noticed rather than slipping through.
    """
    from dashboard.management.commands import import_observations as mod

    monkeypatch.setattr(mod, "BULK_CREATE_CHUNK_SIZE", 3)

    rows = [
        # Chunk 1 (indices 0-3): four brand-new rows, no pre-existing match
        make_raw_row(
            gbif_id=100,
            occurrence_id="chunk-new-0",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
        make_raw_row(
            gbif_id=101,
            occurrence_id="chunk-new-1",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
        make_raw_row(
            gbif_id=102,
            occurrence_id="chunk-new-2",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
        make_raw_row(
            gbif_id=103,
            occurrence_id="chunk-new-3",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
        # Chunk 2 (indices 4-6): replacement lives here (index 5)
        make_raw_row(
            gbif_id=104,
            occurrence_id="chunk-new-4",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
        # Matches observation_unseen_to_be_replaced's stable_id
        _row_replacing_unseen_observation(gbif_id=105),
        make_raw_row(
            gbif_id=106,
            occurrence_id="chunk-new-6",
            dataset_key=INATURALIST_KEY,
            dataset_name="iNaturalist",
            taxon_key=LIXUS_COL_KEY,
            accepted_taxon_key=LIXUS_COL_KEY,
            species_key=LIXUS_COL_KEY,
        ),
    ]

    with mock.patch.object(
        mod,
        "_batch_insert_observations",
        wraps=mod._batch_insert_observations,
    ) as batch_spy:
        run_import_with_rows(rows)

    # Chunking actually happened: 7 rows at CHUNK_SIZE=3 gives 3 + 3 + 1
    assert (
        batch_spy.call_count == 3
    ), f"Expected 3 chunk flushes, got {batch_spy.call_count}"
    assert [len(call.args[0]) for call in batch_spy.call_args_list] == [3, 3, 1]

    # All 7 rows made it to the DB
    assert Observation.objects.count() == 7
    di = DataImport.objects.latest("id")
    assert di.skipped_observations_counter == 0
    assert di.imported_observations_counter == 7

    # Replacement was correctly detected in chunk 2: the comment that
    # was on the pre-existing observation_unseen_to_be_replaced now
    # points to the new row with the same stable_id.
    comment = ObservationComment.objects.get()
    assert (
        comment.observation.occurrence_id
        == "https://www.inaturalist.org/observations/33366292"
    )
    assert comment.observation.data_import == di
    # And the replacement's initial_data_import was preserved from the
    # original import (not reset to the current one).
    assert comment.observation.initial_data_import == test_data["initial_di"]


def test_dataset_cleanup_mechanism(test_data):
    """After import, Dataset objects with no associated observations are
    deleted; alerts referencing those empty datasets are un-referenced."""
    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=1,
                occurrence_id="for-cleanup-test",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
            ),
        ]
    )

    alert = test_data["alert_referencing_unused_dataset"]
    dataset_without_observations = test_data["dataset_without_observations"]

    alert.refresh_from_db()

    with pytest.raises(Dataset.DoesNotExist):
        dataset_without_observations.refresh_from_db()

    assert alert.datasets.count() == 1
    assert alert.datasets.first().gbif_dataset_key == INATURALIST_KEY


def test_basis_of_record_cleanup_mechanism(test_data):
    """After import, BasisOfRecord objects with no associated observations
    are deleted; alerts referencing those empty BoRs are un-referenced.

    Mirror of test_dataset_cleanup_mechanism for the parallel BoR branch
    in run_import.
    """
    # A BoR that's not used by any observation in test_data.
    machine_observation = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")

    # An alert that filters on this (about-to-be-unused) BoR.
    alert = Alert.objects.create(name="Machine-only alert", user=test_data["user"])
    alert.basis_of_record_filters.add(machine_observation)

    # Import one row using HUMAN_OBSERVATION. After import,
    # MACHINE_OBSERVATION still has zero observations and should be
    # cleaned up; the alert's filter set should be cleared.
    run_import_with_rows(
        [
            make_raw_row(
                gbif_id=1,
                occurrence_id="bor-cleanup-new",
                dataset_key=INATURALIST_KEY,
                dataset_name="iNaturalist",
                taxon_key=LIXUS_COL_KEY,
                accepted_taxon_key=LIXUS_COL_KEY,
                species_key=LIXUS_COL_KEY,
                basis_of_record="HUMAN_OBSERVATION",
            ),
        ]
    )

    alert.refresh_from_db()

    with pytest.raises(BasisOfRecord.DoesNotExist):
        machine_observation.refresh_from_db()

    assert alert.basis_of_record_filters.count() == 0
    # HUMAN_OBSERVATION is still around (the new row uses it)
    assert BasisOfRecord.objects.filter(name="HUMAN_OBSERVATION").exists()


def test_transaction(test_data):
    """The whole import runs in one transaction: if it fails near the end,
    no DB changes are persisted."""
    MODELS_TO_OBSERVE = [
        Dataset,
        Species,
        ObservationComment,
        DataImport,
        Observation,
    ]

    models_before = {
        Model._meta.label: list(Model.objects.all().order_by("pk"))
        for Model in MODELS_TO_OBSERVE
    }

    # Clean baseline so the post-failure assertion proves run_import cleared it.
    set_maintenance_mode(False)
    assert get_maintenance_mode() is False

    # DataImport.complete() fires at the very end; force it to raise.
    with mock.patch(
        "dashboard.models.DataImport.complete", side_effect=Exception("Boom!")
    ):
        with pytest.raises(Exception):
            run_import_with_rows(
                [
                    make_raw_row(
                        gbif_id=1,
                        occurrence_id="some-new-occurrence",
                        dataset_key=INATURALIST_KEY,
                        dataset_name="iNaturalist",
                        taxon_key=LIXUS_COL_KEY,
                        accepted_taxon_key=LIXUS_COL_KEY,
                        species_key=LIXUS_COL_KEY,
                    ),
                ]
            )

    # run_import clears maintenance mode even when the import raises: the
    # transaction rolled back, so there is no half-imported state to guard.
    assert get_maintenance_mode() is False

    for Model in MODELS_TO_OBSERVE:
        assert (
            list(Model.objects.all().order_by("pk")) == models_before[Model._meta.label]
        )


@override_settings(ADMINS=[("Admin", "admin@example.com")])
def test_failed_import_clears_maintenance_and_emails_admins(test_data, mailoutbox):
    """A failed import must not fail silently: it clears maintenance mode and
    emails the admins with the exception traceback before re-raising.

    Pins the contract behind the production incident where a crashing import
    left the site stuck in maintenance mode with no notification.
    """
    set_maintenance_mode(False)
    assert get_maintenance_mode() is False

    with mock.patch(
        "dashboard.models.DataImport.complete",
        side_effect=Exception("Boom during import"),
    ):
        with pytest.raises(Exception, match="Boom during import"):
            run_import_with_rows(
                [
                    make_raw_row(
                        gbif_id=1,
                        occurrence_id="fail-1",
                        dataset_key=INATURALIST_KEY,
                        dataset_name="iNaturalist",
                        taxon_key=LIXUS_COL_KEY,
                        accepted_taxon_key=LIXUS_COL_KEY,
                        species_key=LIXUS_COL_KEY,
                    ),
                ]
            )

    # Maintenance mode is cleared despite the failure.
    assert get_maintenance_mode() is False

    # Admins were emailed, and the message carries the exception traceback.
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert "ERROR during observation data import" in email.subject
    assert "Boom during import" in email.body
    assert "admin@example.com" in email.to


def test_import_aborts_when_a_species_lacks_col_key():
    """The preflight guard blocks the whole import when any species lacks a COL
    key, naming it in the error.

    Why all-or-nothing: a download is interpreted against a single taxonomy, so
    a species with no COL key cannot be queried or matched. Importing "the rest"
    would quietly stop monitoring it, so the guard refuses the entire run.
    """
    Species.objects.all().delete()
    Species.objects.create(
        name="Lixus bardanae",
        gbif_taxon_key=LIXUS_KEY,
        gbif_col_taxon_key=LIXUS_COL_KEY,
    )
    Species.objects.create(
        name="Polydrusus planifrons", gbif_taxon_key=POLYDRUSUS_KEY
    )  # no COL key
    with pytest.raises(CommandError) as exc:
        call_command("import_observations")
    assert "Polydrusus planifrons" in str(exc.value)


def test_import_aborts_when_all_missing():
    """Same guard with every species missing the key: the error also names the
    conversion command, so an un-migrated instance tells the operator what to
    run rather than firing a broken download."""
    Species.objects.all().delete()
    Species.objects.create(name="Lixus bardanae", gbif_taxon_key=LIXUS_KEY)
    with pytest.raises(CommandError) as exc:
        call_command("import_observations")
    assert "convert_taxon_keys_to_col" in str(exc.value)


def test_import_aborts_when_a_species_has_blank_col_key():
    """A blank ("") COL key counts as missing, not as a valid key.

    Why: a "" would pass a NULL-only check, then be dropped from the species
    match hash and injected as an empty value into the download predicate -
    silently unmonitoring the species. The row is forced via .update() to
    bypass the model's save()-normalisation, mimicking a pre-existing blank.
    """
    Species.objects.all().delete()
    Species.objects.create(
        name="Lixus bardanae",
        gbif_taxon_key=LIXUS_KEY,
        gbif_col_taxon_key=LIXUS_COL_KEY,
    )
    blank = Species.objects.create(
        name="Polydrusus planifrons",
        gbif_taxon_key=POLYDRUSUS_KEY,
        gbif_col_taxon_key=POLYDRUSUS_COL_KEY,
    )
    Species.objects.filter(pk=blank.pk).update(gbif_col_taxon_key="")
    with pytest.raises(CommandError) as exc:
        call_command("import_observations")
    assert "Polydrusus planifrons" in str(exc.value)


def test_import_vacuum_analyzes_the_rewritten_tables(test_data):
    """The import ends by vacuuming the two tables it rewrites wholesale.

    Why it matters: the import replaces every observation row, so on commit the
    visibility map still describes the previous dataset and index-only scans
    degrade into a heap fetch per index entry until something vacuums. VACUUM
    cannot run inside a transaction, so this also pins that the call happens
    after the import transaction has committed.
    """
    executed: list[str] = []
    real_execute = type(connection.cursor()).execute

    def spy(self, sql, params=None):
        if isinstance(sql, str) and sql.startswith("VACUUM"):
            executed.append(sql)
            assert (
                not connection.in_atomic_block
            ), "VACUUM was issued inside a transaction; it cannot run there"
            return None
        return real_execute(self, sql, params)

    with mock.patch.object(type(connection.cursor()), "execute", spy):
        run_import_with_rows(
            [
                make_raw_row(
                    gbif_id=1,
                    occurrence_id="some-new-occurrence",
                    dataset_key=INATURALIST_KEY,
                    dataset_name="iNaturalist",
                    taxon_key=LIXUS_COL_KEY,
                    accepted_taxon_key=LIXUS_COL_KEY,
                    species_key=LIXUS_COL_KEY,
                ),
            ]
        )

    assert executed == [
        "VACUUM (ANALYZE) dashboard_observation",
        "VACUUM (ANALYZE) dashboard_observationunseen",
    ]


def test_import_survives_a_failing_vacuum(test_data):
    """A vacuum problem must not fail an import that already committed.

    The data is in and the site is back up by then; autovacuum will catch up.
    """
    with mock.patch(
        "dashboard.management.commands.import_observations.connection"
    ) as fake_connection:
        fake_connection.in_atomic_block = False
        fake_connection.cursor.side_effect = Exception("no privileges to vacuum")

        data_import = run_import_with_rows(
            [
                make_raw_row(
                    gbif_id=1,
                    occurrence_id="some-new-occurrence",
                    dataset_key=INATURALIST_KEY,
                    dataset_name="iNaturalist",
                    taxon_key=LIXUS_COL_KEY,
                    accepted_taxon_key=LIXUS_COL_KEY,
                    species_key=LIXUS_COL_KEY,
                ),
            ]
        )

    # The import itself completed and committed.
    assert Observation.objects.filter(data_import=data_import).count() == 1
