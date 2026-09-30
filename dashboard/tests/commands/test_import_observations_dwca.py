"""Import tests that exercise the real DwCA zip format.

Scope is deliberately narrow: this file covers DwCA parsing + metadata
extraction, the GBIF HTTP flow, and one real-world end-to-end smoke test.
Business-logic tests (skip rules, seen/unseen, comment/unseen migration,
dataset cleanup, transaction rollback) live in
test_import_observations_logic.py and are driven by in-memory
RawObservationRow fixtures - they don't need the zip.
"""

import io
import os
import shutil
from pathlib import Path
from unittest import mock

import pytest
import requests_mock as requests_mock_module
from django.core.management import CommandError, call_command
from django.test import override_settings
from maintenance_mode.core import (  # type: ignore
    get_maintenance_mode,
    set_maintenance_mode,
)

from dashboard.models import (
    DataImport,
    Observation,
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

    call_command(
        "import_observations", source_dwca=str(SAMPLE_DATA_PATH / "gbif_download.zip")
    )

    assert Observation.objects.all().count() == 7

    assert DataImport.objects.latest("id").skipped_observations_counter == 6
    # TODO: more testing to make sure it's the usable ones that were loaded?


def test_load_observations_values(test_data) -> None:
    """Imported values look correct"""
    call_command(
        "import_observations", source_dwca=str(SAMPLE_DATA_PATH / "gbif_download.zip")
    )

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

    occ = observations[2]  # Fourth row in CSV (third was skipped because of date issue)

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
    call_command(
        "import_observations", source_dwca=str(SAMPLE_DATA_PATH / "gbif_download.zip")
    )

    di = DataImport.objects.latest("id")
    assert di.start is not None
    assert di.end is not None
    assert di.end > di.start
    assert di.completed
    assert di.gbif_download_id == "0076720-210914110416597"
    assert di.gbif_predicate is None
    assert (
        di.imported_observations_counter
        == Observation.objects.filter(data_import=di).count()
    )


def test_gbif_request_not_necessary(test_data) -> None:
    """No HTTP request emitted if the --source-dwca option is used"""
    with requests_mock_module.Mocker() as m:
        call_command(
            "import_observations",
            source_dwca=str(SAMPLE_DATA_PATH / "gbif_download.zip"),
        )
        request_history = m.request_history
        assert len(request_history) == 0


def test_gbif_request(test_data, gbif_download_config) -> None:
    """The correct HTTP requests are emitted to gbif.org"""
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
        with requests_mock_module.Mocker() as m:
            m.post("https://api.gbif.org/v1/occurrence/download/request", text="1000")
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
                '{"type": "in", "key": "TAXON_KEY", "values": ["3VPFV", "4L6VJ"], '
                '"checklistKey": "7ddf754f-d193-4cc9-b351-99906754a03b"}, '
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
            m.post("https://api.gbif.org/v1/occurrence/download/request", text="1000")
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
                            "values": ["3VPFV", "4L6VJ"],
                            "checklistKey": "7ddf754f-d193-4cc9-b351-99906754a03b",
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


# ---------------------------------------------------------------------------
# Source archive lifecycle: an archive the command downloaded itself is a temp
# file and must be deleted whatever happens; a file passed with --source-dwca
# belongs to the operator and must never be touched.
# ---------------------------------------------------------------------------


def _fake_download(output_paths: list[str]):
    """Stand-in for the GBIF download: copies the sample archive to the path
    the command asked for and records that path."""

    def fake(predicate, username, password, output_path, max_wait):
        output_paths.append(output_path)
        shutil.copyfile(SAMPLE_DATA_PATH / "gbif_download.zip", output_path)

    return fake


def test_downloaded_dwca_deleted_when_import_fails(
    test_data, gbif_download_config
) -> None:
    from dashboard.management.commands import import_observations as mod

    downloaded: list[str] = []
    with mock.patch.object(
        mod, "download_gbif_occurrences", side_effect=_fake_download(downloaded)
    ):
        with mock.patch.object(mod, "run_import", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                call_command("import_observations")

    assert len(downloaded) == 1
    assert not os.path.exists(downloaded[0])


def test_downloaded_dwca_deleted_when_download_fails(
    test_data, gbif_download_config
) -> None:
    from dashboard.management.commands import import_observations as mod

    requested: list[str] = []

    def failing_download(predicate, username, password, output_path, max_wait):
        requested.append(output_path)
        raise RuntimeError("gbif down")

    with mock.patch.object(
        mod, "download_gbif_occurrences", side_effect=failing_download
    ):
        with pytest.raises(RuntimeError, match="gbif down"):
            call_command("import_observations")

    assert len(requested) == 1
    assert not os.path.exists(requested[0])


def test_downloaded_dwca_deleted_on_success(test_data, gbif_download_config) -> None:
    from dashboard.management.commands import import_observations as mod

    downloaded: list[str] = []
    with mock.patch.object(
        mod, "download_gbif_occurrences", side_effect=_fake_download(downloaded)
    ):
        call_command("import_observations")

    assert len(downloaded) == 1
    assert not os.path.exists(downloaded[0])
    assert Observation.objects.count() == 7


def test_user_provided_dwca_kept_when_import_fails(test_data, tmp_path) -> None:
    from dashboard.management.commands import import_observations as mod

    user_file = tmp_path / "my_download.zip"
    shutil.copyfile(SAMPLE_DATA_PATH / "gbif_download.zip", user_file)

    with mock.patch.object(mod, "run_import", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            call_command("import_observations", source_dwca=str(user_file))

    assert user_file.exists()


def test_user_provided_dwca_kept_on_success(test_data, tmp_path) -> None:
    user_file = tmp_path / "my_download.zip"
    shutil.copyfile(SAMPLE_DATA_PATH / "gbif_download.zip", user_file)

    call_command("import_observations", source_dwca=str(user_file))

    assert user_file.exists()
    assert Observation.objects.count() == 7


# ---------------------------------------------------------------------------
# Error email: whatever step fails, the admins get exactly one email (#481).
# ---------------------------------------------------------------------------


@override_settings(
    ADMINS=[("Admin", "admin@example.com")], GBIF_DOWNLOAD_MAX_WAIT_HOURS=2
)
def test_stuck_download_gives_up_and_emails_admins(
    test_data, gbif_download_config, mailoutbox
) -> None:
    """A download that never becomes ready is abandoned after the configured
    wait, and the admins are told - the previous data stays online, so nothing
    else would reveal that it stopped refreshing."""
    from dashboard.management.commands import import_observations as mod

    max_waits: list[float] = []

    def stuck_download(predicate, username, password, output_path, max_wait):
        max_waits.append(max_wait)
        raise TimeoutError("still not ready")

    with mock.patch.object(
        mod, "download_gbif_occurrences", side_effect=stuck_download
    ):
        with pytest.raises(TimeoutError):
            call_command("import_observations")

    assert max_waits == [2 * 60 * 60]
    assert len(mailoutbox) == 1
    assert "(GBIF download)" in mailoutbox[0].subject
    assert "still not ready" in mailoutbox[0].body


@override_settings(ADMINS=[("Admin", "admin@example.com")])
def test_failed_database_import_clears_maintenance_and_emails_admins_once(
    test_data, mailoutbox
) -> None:
    """A failed import must not fail silently: it clears maintenance mode and
    emails the admins with the exception traceback before re-raising.

    Pins the contract behind the production incident where a crashing import
    left the site stuck in maintenance mode with no notification. Exactly one
    email: run_import() re-raises, and only handle() reports.
    """
    set_maintenance_mode(False)

    with mock.patch(
        "dashboard.models.DataImport.complete",
        side_effect=Exception("Boom during import"),
    ):
        with pytest.raises(Exception, match="Boom during import"):
            call_command(
                "import_observations",
                source_dwca=str(SAMPLE_DATA_PATH / "gbif_download.zip"),
            )

    assert get_maintenance_mode() is False
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert "ERROR during observation data import (database import)" in email.subject
    assert "Boom during import" in email.body
    assert "admin@example.com" in email.to


def test_missing_user_provided_dwca_rejected(test_data, tmp_path) -> None:
    """A --source-dwca path that doesn't exist fails before any import"""
    imports_before = DataImport.objects.count()

    with pytest.raises(CommandError, match="DwC-A file not found"):
        call_command("import_observations", source_dwca=str(tmp_path / "nope.zip"))

    assert DataImport.objects.count() == imports_before


def test_source_dwca_url(test_data) -> None:
    """--source-dwca also takes a URL: the archive is fetched, imported, and
    the temporary copy deleted. The GBIF URLs of the download are logged."""
    from dashboard.management.commands import import_observations as mod

    url = "https://example.org/gbif_download.zip"
    out = io.StringIO()
    with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as archive:
        with requests_mock_module.Mocker() as m:
            m.get(url, body=archive)
            with mock.patch.object(
                mod, "_download_dwca", wraps=mod._download_dwca
            ) as download:
                call_command("import_observations", source_dwca=url, stdout=out)

    assert Observation.objects.count() == 7
    assert not os.path.exists(download.call_args.args[1])
    logs = out.getvalue()
    assert "https://www.gbif.org/occurrence/download/0076720-210914110416597" in logs
    assert (
        "https://api.gbif.org/v1/occurrence/download/request/0076720-210914110416597.zip"
        in logs
    )


def test_source_dwca_url_download_fails(test_data) -> None:
    """A --source-dwca URL that cannot be fetched fails before any import"""
    imports_before = DataImport.objects.count()
    url = "https://example.org/nope.zip"

    with requests_mock_module.Mocker() as m:
        m.get(url, status_code=404)
        with pytest.raises(CommandError, match="Could not download the DwC-A"):
            call_command("import_observations", source_dwca=url)

    assert DataImport.objects.count() == imports_before
