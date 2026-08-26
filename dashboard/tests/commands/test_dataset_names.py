"""Tests for resolving Dataset names from the GBIF registry.

Most GBIF publishers leave the verbatim dwc:datasetName field empty, so an
occurrence download carries a dataset key but no dataset title. These tests
cover the lookup helper that fills the gap and the pipeline step that uses it.
"""

from io import StringIO
from unittest import mock

import pytest
import requests
from django.core.management import call_command

from dashboard.management.commands.helpers import (
    fill_missing_dataset_names,
    get_dataset_name_from_gbif_api,
)
from dashboard.models import Dataset
from dashboard.tests.commands.factories import make_raw_row, run_import_with_rows

pytestmark = pytest.mark.django_db


class TestGetDatasetNameFromGbifApi:
    def test_returns_the_registry_title(self):
        response = mock.Mock()
        response.json.return_value = {"title": "alien_plant_ro"}
        with mock.patch("requests.get", return_value=response) as get:
            name = get_dataset_name_from_gbif_api("ccfe7801-5c44-4df5-90e2-cdffb0d5735")

        assert name == "alien_plant_ro"
        assert (
            get.call_args.args[0]
            == "https://api.gbif.org/v1/dataset/ccfe7801-5c44-4df5-90e2-cdffb0d5735"
        )

    def test_uses_a_timeout(self):
        """Without one, a hanging GBIF API would hang the import forever."""
        response = mock.Mock()
        response.json.return_value = {"title": "whatever"}
        with mock.patch("requests.get", return_value=response) as get:
            get_dataset_name_from_gbif_api("some-key")

        assert get.call_args.kwargs.get("timeout")

    def test_returns_empty_string_when_the_request_fails(self):
        with mock.patch("requests.get", side_effect=requests.Timeout("too slow")):
            assert get_dataset_name_from_gbif_api("some-key") == ""

    def test_returns_empty_string_when_the_key_is_unknown(self):
        """GBIF answers an unknown key with a payload that has no title."""
        response = mock.Mock()
        response.json.return_value = {}
        with mock.patch("requests.get", return_value=response):
            assert get_dataset_name_from_gbif_api("not-a-key") == ""


class TestFillMissingDatasetNames:
    def test_fills_blank_names_from_the_registry(self):
        blank = Dataset.objects.create(gbif_dataset_key="key-blank", name="")

        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="Resolved title",
        ):
            updated = fill_missing_dataset_names()

        blank.refresh_from_db()
        assert blank.name == "Resolved title"
        assert updated == 1

    def test_leaves_already_named_datasets_alone(self):
        named = Dataset.objects.create(gbif_dataset_key="key-named", name="Known name")

        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="Should not be used",
        ) as lookup:
            fill_missing_dataset_names()

        named.refresh_from_db()
        assert named.name == "Known name"
        lookup.assert_not_called()

    def test_a_dataset_the_registry_cannot_name_stays_blank(self):
        blank = Dataset.objects.create(gbif_dataset_key="key-blank", name="")

        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="",
        ):
            updated = fill_missing_dataset_names()

        blank.refresh_from_db()
        assert blank.name == ""
        assert updated == 0

    def test_one_failing_lookup_does_not_stop_the_others(self):
        """An unexpected error on one key must not leave the rest unnamed."""
        first = Dataset.objects.create(gbif_dataset_key="key-a", name="")
        second = Dataset.objects.create(gbif_dataset_key="key-b", name="")

        def lookup(key: str) -> str:
            if key == "key-a":
                raise ValueError("boom")
            return "Second dataset"

        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            side_effect=lookup,
        ):
            updated = fill_missing_dataset_names()

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.name == ""
        assert second.name == "Second dataset"
        assert updated == 1


class TestImportFillsDatasetNames:
    """The import pipeline's end of the same story.

    These drive run_import through the shared row factories, so they need the
    transactional django_db mode the other import tests use.
    """

    pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.sequential]

    def test_a_download_without_a_dataset_name_still_names_the_dataset(self, test_data):
        """The end-to-end symptom: GBIF sends an empty dwc:datasetName, and the
        dataset must not be left blank in the filter list."""
        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="alien_plant_ro",
        ):
            run_import_with_rows(
                [
                    make_raw_row(
                        occurrence_id="no-dataset-name",
                        dataset_key="ccfe7801-5c44-4df5-90e2-cdffb0d57352",
                        dataset_name="",
                    )
                ]
            )

        dataset = Dataset.objects.get(
            gbif_dataset_key="ccfe7801-5c44-4df5-90e2-cdffb0d57352"
        )
        assert dataset.name == "alien_plant_ro"

    def test_an_empty_dataset_name_does_not_blank_a_known_one(self, test_data):
        """Once named, a dataset keeps its name even if GBIF is unreachable on
        the next import - otherwise every import would blank it again."""
        Dataset.objects.create(gbif_dataset_key="ds-key-known", name="Known name")

        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="",
        ):
            run_import_with_rows(
                [
                    make_raw_row(
                        occurrence_id="known-dataset",
                        dataset_key="ds-key-known",
                        dataset_name="",
                    )
                ]
            )

        assert Dataset.objects.get(gbif_dataset_key="ds-key-known").name == "Known name"

    def test_a_dataset_name_present_in_the_download_is_used_as_is(self, test_data):
        """No registry lookup when the publisher did supply dwc:datasetName."""
        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="Registry title",
        ) as lookup:
            run_import_with_rows(
                [
                    make_raw_row(
                        occurrence_id="with-dataset-name",
                        dataset_key="ds-key-named",
                        dataset_name="Name from the download",
                    )
                ]
            )

        assert (
            Dataset.objects.get(gbif_dataset_key="ds-key-named").name
            == "Name from the download"
        )
        lookup.assert_not_called()


class TestSyncDatasetNamesCommand:
    """The manual escape hatch: name existing blanks without a full re-import."""

    def test_names_the_blank_datasets_and_reports_how_many(self):
        blank = Dataset.objects.create(gbif_dataset_key="key-blank", name="")
        named = Dataset.objects.create(gbif_dataset_key="key-named", name="Known name")
        out = StringIO()

        with mock.patch(
            "dashboard.management.commands.helpers.get_dataset_name_from_gbif_api",
            return_value="Resolved title",
        ):
            call_command("sync_dataset_names", stdout=out)

        blank.refresh_from_db()
        named.refresh_from_db()
        assert blank.name == "Resolved title"
        assert named.name == "Known name"
        assert "1" in out.getvalue()
