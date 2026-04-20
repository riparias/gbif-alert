import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import requests_mock as requests_mock_module
from django.core.management import call_command

from dashboard.models import (
    Alert,
    DataImport,
    Dataset,
    Observation,
    ObservationUnseen,
    Species,
)

THIS_SCRIPT_PATH = Path(__file__).parent
SAMPLE_DATA_PATH = THIS_SCRIPT_PATH / "sample_data"

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.sequential]


def test_ignore_unusable_observations(test_data) -> None:
    """The DwC-A contains 13 records, but some are not usable:

    - missing coordinates: 3 records
    - no year: 1 record
    - no occurrence ID: 1 record
    - absence: 1 record

    => so, only 7 should be loaded after the import process
    """

    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    assert Observation.objects.all().count() == 7

    assert DataImport.objects.latest("id").skipped_observations_counter == 6
    # TODO: more testing to make sure it's the usable ones that were loaded?


def test_load_observations_values(test_data) -> None:
    """Imported values look correct"""
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    observations = Observation.objects.all().order_by("id")
    # We assume observations are loaded in the DwC-A rows order
    occ = observations[0]
    assert str(occ.date) == "2024-10-10"
    assert occ.gbif_id == "3044795455"
    assert occ.occurrence_id == "https://www.inaturalist.org/observations/42671325"
    assert occ.stable_id == "4aa3b8d81c4a62c89b73a4416af7d51968c29104"
    assert (
        occ.species_id == test_data["polydrusus"].pk
    )  # This also test the fallback to the acceptedTaxonKey (https://github.com/riparias/gbif-alert/issues/93)
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(3.315567)  # type: ignore
    assert lat == pytest.approx(51.354473)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    # The dataset name has been updated (compared to test data) because it was updated from the name in the
    # DwC-A (https://github.com/riparias/gbif-alert/issues/257)
    assert occ.source_dataset.name == "iNaturalist research-grade observations"

    occ = observations[1]
    assert str(occ.date) == "2020-04-19"
    assert occ.gbif_id == "2609350465"
    assert occ.occurrence_id == "https://www.inaturalist.org/observations/42577016"
    assert occ.stable_id == "6a6fc5bd50d1ead0f33f32c843b185bbfbd7c166"
    assert (
        occ.species_id == test_data["polydrusus"].pk
    )  # This also test the fallback to the speciesKey (https://github.com/riparias/gbif-alert/issues/93)
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(3.254023)  # type: ignore
    assert lat == pytest.approx(50.664364)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    assert occ.source_dataset.name == "iNaturalist research-grade observations"
    assert occ.references == "https://www.inaturalist.org/observations/42577016"

    occ = observations[
        2
    ]  # Fourth row in CSV (third was skipped because of date issue)

    assert str(occ.date) == "2018-05-05"
    assert occ.gbif_id == "2423231120"
    assert occ.occurrence_id == "https://www.inaturalist.org/observations/33366292"
    assert occ.stable_id == "a4ec033c2da60ef1095c50f4445bf305904aa336"
    assert occ.species_id == test_data["polydrusus"].pk
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(3.52526)  # type: ignore
    assert lat == pytest.approx(51.150846)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    assert occ.source_dataset.name == "iNaturalist research-grade observations"

    occ = observations[3]

    assert str(occ.date) == "2018-09-05"
    assert occ.gbif_id == "1914197587"
    assert occ.occurrence_id == "https://www.inaturalist.org/observations/16227955"
    assert occ.stable_id == "48f6d956f104c4c83174e9ea7cbb0b545e995d4d"
    assert occ.species_id == test_data["lixus"].pk
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(4.360086)  # type: ignore
    assert lat == pytest.approx(50.646894)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    assert occ.source_dataset.name == "iNaturalist research-grade observations"
    assert occ.recorded_by == "Nicolas Noé"
    assert occ.basis_of_record.name == "HUMAN_OBSERVATION"
    assert occ.locality == "Lillois"
    assert occ.municipality == "Braine L'alleud"
    assert occ.individual_count == 1
    assert occ.coordinate_uncertainty_in_meters == 23

    occ = observations[4]

    assert str(occ.date) == "2018-05-11"
    assert occ.gbif_id == "1847507314"
    assert occ.occurrence_id == "https://www.inaturalist.org/observations/12411012"
    assert occ.stable_id == "baddab78a96bf75f3dd98b0be69b035364f6a77e"
    assert occ.species_id == test_data["polydrusus"].pk
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(2.59858)  # type: ignore
    assert lat == pytest.approx(51.097573)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    assert occ.source_dataset.name == "iNaturalist research-grade observations"

    occ = observations[5]

    assert str(occ.date) == "2017-05-15"
    assert occ.gbif_id == "1802743867"
    assert occ.occurrence_id == "https://www.inaturalist.org/observations/9294095"
    assert occ.stable_id == "85b4076d572cdc8782746d3dc0252fab7e2a5cd2"
    assert occ.species_id == test_data["polydrusus"].pk
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(4.454613)  # type: ignore
    assert lat == pytest.approx(51.26503)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    assert occ.source_dataset.name == "iNaturalist research-grade observations"

    occ = observations[6]

    assert str(occ.date) == "1950-06-18"
    assert occ.gbif_id == "1315928743"
    assert occ.occurrence_id == "Ugent:UGMD:16879"
    assert occ.stable_id == "cc478993ca998a9be116bad94e6b31ddf2128f33"
    assert occ.species_id == test_data["lixus"].pk
    lon, lat = occ.lonlat_4326_tuple
    assert lon == pytest.approx(4.418141)  # type: ignore
    assert lat == pytest.approx(51.27734)  # type: ignore
    assert occ.data_import_id == DataImport.objects.latest("id").id
    assert (
        occ.source_dataset.name
        == "Ghent university - Zoology Museum - Insect Collection"
    )
    # We stop there, the remaining rows in DwC-A miss either the location or the occurrence id


def test_dataimport_object_values(test_data):
    """Values of the DataImport object are created

    Side effect of the observations_counter check: we also check that newly created observations reference the
    correct DataImport object
    """
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    di = DataImport.objects.latest("id")
    assert di.start is not None
    assert di.end is not None
    assert di.end > di.start
    assert di.completed
    assert di.gbif_download_id == "0076720-210914110416597"
    assert di.gbif_predicate is None
    assert di.imported_observations_counter == Observation.objects.filter(
        data_import=di
    ).count()


def test_gbif_request_not_necessary(test_data) -> None:
    """No HTTP request emitted if the --source-dwca option is used"""
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        with requests_mock_module.Mocker() as m:
            call_command(
                "import_observations",
                source_dwca=gbif_download_file,
            )
            request_history = m.request_history
            assert len(request_history) == 0


def test_seen_status_unseen_to_seen_age(test_data) -> None:
    """An old unseen observation is marked as seen after import (because it's older than the user delay)"""
    # user delay is the default (365 days)
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    observations_after = Observation.objects.all()
    obs = observations_after.get(
        occurrence_id=test_data["observation_unseen_to_be_replaced"].occurrence_id
    )

    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=obs, user=test_data["user"])


def test_seen_status_unseen_to_unseen(test_data) -> None:
    """Same situation than test_seen_status_unseen_to_seen_age() but we force the
    user delay to be very long, so the unseen status is kept"""
    user = test_data["user"]
    user.notification_delay_days = 365 * 20
    user.save()

    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    observations_after = Observation.objects.all()
    obs = observations_after.get(
        occurrence_id=test_data["observation_unseen_to_be_replaced"].occurrence_id
    )

    ObservationUnseen.objects.get(observation=obs, user=user)


def test_seen_status_seen_to_seen(test_data) -> None:
    """An observation that was already seen remains seen after import"""
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    observations_after = Observation.objects.all()

    # Case 1: An existing seen observation has been replaced, it should be marked as seen
    case1 = observations_after.get(
        occurrence_id=test_data["observation_seen_to_be_replaced"].occurrence_id
    )
    # Case 1 result: unseen not found => seen
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(observation=case1, user=test_data["user"])


def test_seen_status_new_to_seen_because_no_alert(test_data) -> None:
    """New observation in the system. It's more recent than the user delay, but is
    not part of any alert, so it's marked as seen"""

    # Make sure we don't have any lingering alert
    Alert.objects.filter(user=test_data["user"]).delete()

    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    observations_after = Observation.objects.all()
    last_di = DataImport.objects.latest("id")

    # Those are the observations that are totally new in the system
    fresh_observations = observations_after.filter(initial_data_import=last_di)

    recent_observation_not_in_alerts = fresh_observations.get(
        stable_id="4aa3b8d81c4a62c89b73a4416af7d51968c29104"
    )

    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(
            observation=recent_observation_not_in_alerts, user=test_data["user"]
        )


def test_seen_status_new_to_seen_because_old(test_data) -> None:
    """New observation in the system. It's older than the user delay, so it's
    marked as seen (even if it's part of an alert)"""

    # We create an alert that matches the observation (all lixus bardanae observations)
    alert = Alert.objects.create(
        user=test_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(test_data["lixus"])

    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    observations_after = Observation.objects.all()
    last_di = DataImport.objects.latest("id")

    # Those are the observations that are totally new in the system
    fresh_observations = observations_after.filter(initial_data_import=last_di)

    old_lixus_bardanae = fresh_observations.get(occurrence_id="Ugent:UGMD:16879")

    # It is considered seen because it's older than the user delay
    with pytest.raises(ObservationUnseen.DoesNotExist):
        ObservationUnseen.objects.get(
            observation=old_lixus_bardanae, user=test_data["user"]
        )


def test_seen_status_new_to_unseen(test_data) -> None:
    """New observation in the system. It's more recent than the user delay, and is
    part of an alert, so it's marked as unseen"""

    # Test code: identical to test_seen_status_new_to_seen_because_old() but we
    # pretend we're running the import in 1950
    alert = Alert.objects.create(
        user=test_data["user"], email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(test_data["lixus"])

    mocked = datetime.datetime(1950, 7, 1, tzinfo=ZoneInfo("UTC"))
    with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
        with open(
            SAMPLE_DATA_PATH / "gbif_download.zip", "rb"
        ) as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

    observations_after = Observation.objects.all()
    last_di = DataImport.objects.latest("id")

    # Those are the observations that are totally new in the system
    fresh_observations = observations_after.filter(initial_data_import=last_di)

    old_lixus_bardanae = fresh_observations.get(occurrence_id="Ugent:UGMD:16879")

    # It is considered not seen because it's only a few days old
    ObservationUnseen.objects.get(observation=old_lixus_bardanae, user=test_data["user"])


def test_gbif_request(test_data, gbif_download_config) -> None:
    """The correct HTTP requests are emitted to gbif.org"""
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        with requests_mock_module.Mocker() as m:
            m.post(
                "https://api.gbif.org/v1/occurrence/download/request", text="1000"
            )
            m.get(
                "https://api.gbif.org/v1/occurrence/download/request/1000",
                body=gbif_download_file,
            )

            call_command("import_observations")

            request_history = m.request_history

            # 1. A request for a new download with the correct filters was sent first
            assert request_history[0].method == "POST"
            assert (
                request_history[0].url
                == "https://api.gbif.org/v1/occurrence/download/request"
            )
            assert request_history[0].text == (
                '{"predicate": {"type": "and", "predicates": ['
                '{"type": "equals", "key": "COUNTRY", "value": "BE"}, '
                '{"type": "in", "key": "TAXON_KEY", "values": ["1224034", "7972617"]}, '
                '{"type": "equals", "key": "OCCURRENCE_STATUS", "value": "present"}, '
                '{"type": "greaterThanOrEquals", "key": "YEAR", "value": 2010}]}}'
            )

            # 2. A request to download the DwCA file was subsequently emitted
            assert request_history[1].method == "GET"
            assert (
                request_history[1].url
                == "https://api.gbif.org/v1/occurrence/download/request/1000"
            )


def test_gbif_predicate_stored(test_data, gbif_download_config):
    """In case of GBIF request, the predicate is stored in the DataImport object"""
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        with requests_mock_module.Mocker() as m:
            m.post(
                "https://api.gbif.org/v1/occurrence/download/request", text="1000"
            )
            m.get(
                "https://api.gbif.org/v1/occurrence/download/request/1000",
                body=gbif_download_file,
            )

            call_command("import_observations")

            di = DataImport.objects.latest("id")
            assert di.gbif_predicate == {
                "predicate": {
                    "type": "and",
                    "predicates": [
                        {"key": "COUNTRY", "type": "equals", "value": "BE"},
                        {
                            "key": "TAXON_KEY",
                            "type": "in",
                            "values": ["1224034", "7972617"],
                        },
                        {
                            "key": "OCCURRENCE_STATUS",
                            "type": "equals",
                            "value": "present",
                        },
                        {
                            "key": "YEAR",
                            "type": "greaterThanOrEquals",
                            "value": 2010,
                        },
                    ],
                }
            }


def test_dataset_cleanup_mechanism(test_data):
    """At the end of the import process, datasets that have no longer any associated observations are deleted

    Alerts referencing those empty datasets are updated appropriately
    """
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        call_command("import_observations", source_dwca=gbif_download_file)

    alert_referencing_unused_dataset = test_data["alert_referencing_unused_dataset"]
    dataset_without_observations = test_data["dataset_without_observations"]

    alert_referencing_unused_dataset.refresh_from_db()

    with pytest.raises(Dataset.DoesNotExist):
        dataset_without_observations.refresh_from_db()

    assert alert_referencing_unused_dataset.datasets.count() == 1
    assert (
        alert_referencing_unused_dataset.datasets.first().gbif_dataset_key
        == "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
    )
