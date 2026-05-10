"""
Tests for import_inat_observations management command and inat_api helpers.
"""

import datetime
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.inat_api import get_inat_taxon_id, _parse_location_from_obs, get_observations
from dashboard.management.commands.import_inat_observations import (
    build_observation_from_inat,
    INAT_DATASET_KEY,
    INAT_BASIS_OF_RECORD,
)
from dashboard.models import (
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    Species,
)


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

INAT_SETTINGS = {
    "SITE_NAME": "Test site",
    "NAVBAR_BACKGROUND_COLOR": "#000",
    "NAVBAR_LIGHT_TEXT": True,
    "ENABLED_LANGUAGES": ("en",),
    "GBIF_DOWNLOAD_CONFIG": {
        "USERNAME": "x",
        "PASSWORD": "x",
        "PREDICATE_BUILDER": lambda qs: {},
    },
    "INAT_IMPORT_CONFIG": {
        "ENABLED": True,
        "PLACE_ID": 6986,
        "QUALITY_GRADES": ["research"],
        "REQUESTS_PER_MINUTE": 999,  # No real throttling in tests
    },
    "MAIN_MAP_CONFIG": {"initialZoom": 8, "initialLat": 50.5, "initialLon": 4.47},
}


def make_inat_obs(
    obs_id: int = 1,
    uuid: str = "aaaabbbb-0000-0000-0000-000000000001",
    taxon_id: int = 999,
    quality_grade: str = "research",
    observed_on: str = "2024-06-15",
    lat: str = "50.5",
    lon: str = "4.5",
    obscured: bool = False,
    username: str = "testuser",
) -> dict:
    """Return a minimal iNat API observation dict."""
    return {
        "id": obs_id,
        "uuid": uuid,
        "quality_grade": quality_grade,
        "observed_on": observed_on,
        "location": f"{lat},{lon}" if not obscured else None,
        "obscured": obscured,
        "user": {"login": username},
        "place_guess": "Brussels",
        "positional_accuracy": 10,
        "uri": f"https://www.inaturalist.org/observations/{obs_id}",
        "taxon": {"id": taxon_id},
    }


# ---------------------------------------------------------------------------
# inat_api module tests
# ---------------------------------------------------------------------------


class GetInatTaxonIdTest(TestCase):
    """Unit tests for get_inat_taxon_id() — all HTTP mocked."""

    def _mock_taxa_response(self, results: list) -> dict:
        return {"total_results": len(results), "results": results}

    @patch("dashboard.inat_api._get")
    def test_matches_by_gbif_id(self, mock_get):
        mock_get.return_value = self._mock_taxa_response([
            {"id": 12345, "name": "Vespa velutina", "gbif_id": 1311477},
        ])
        result = get_inat_taxon_id(gbif_taxon_key=1311477, scientific_name="Vespa velutina")
        self.assertEqual(result, 12345)

    @patch("dashboard.inat_api._get")
    def test_falls_back_to_name_match(self, mock_get):
        mock_get.return_value = self._mock_taxa_response([
            {"id": 99999, "name": "Vespa velutina", "gbif_id": None},
        ])
        result = get_inat_taxon_id(gbif_taxon_key=1311477, scientific_name="Vespa velutina")
        self.assertEqual(result, 99999)

    @patch("dashboard.inat_api._get")
    def test_returns_none_when_not_found(self, mock_get):
        mock_get.return_value = self._mock_taxa_response([])
        result = get_inat_taxon_id(gbif_taxon_key=1311477, scientific_name="Unknown species")
        self.assertIsNone(result)

    @patch("dashboard.inat_api._get")
    def test_prefers_gbif_id_match_over_name_match(self, mock_get):
        mock_get.return_value = self._mock_taxa_response([
            {"id": 11111, "name": "Vespa velutina", "gbif_id": None},
            {"id": 22222, "name": "Vespa velutina nigrithorax", "gbif_id": 1311477},
        ])
        result = get_inat_taxon_id(gbif_taxon_key=1311477, scientific_name="Vespa velutina")
        self.assertEqual(result, 22222)


class ParseLocationTest(TestCase):
    """Unit tests for location parsing from iNat observation dicts."""

    def _loc(self, **kwargs):
        """Build a minimal obs dict and call _parse_location_from_obs via build_observation_from_inat."""
        return make_inat_obs(**kwargs)

    def test_normal_location_parsed(self):
        from dashboard.inat_api import _parse_location_from_obs  # noqa: re-import for clarity
        # Use the private helper indirectly through the public function result
        obs = make_inat_obs(lat="50.5", lon="4.5", obscured=False)
        point = _parse_location_from_obs(obs)
        self.assertIsNotNone(point)
        self.assertAlmostEqual(point.x, 4.5)
        self.assertAlmostEqual(point.y, 50.5)

    def test_obscured_returns_none(self):
        from dashboard.inat_api import _parse_location_from_obs
        obs = make_inat_obs(obscured=True)
        self.assertIsNone(_parse_location_from_obs(obs))

    def test_missing_location_returns_none(self):
        from dashboard.inat_api import _parse_location_from_obs
        obs = make_inat_obs()
        obs["location"] = None
        self.assertIsNone(_parse_location_from_obs(obs))


# ---------------------------------------------------------------------------
# build_observation_from_inat tests
# ---------------------------------------------------------------------------


class BuildObservationFromInatTest(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            name="Vespa velutina", gbif_taxon_key=1311477, inat_taxon_id=119019
        )
        self.di = DataImport.objects.create(
            start=timezone.now(), source=DataImport.SOURCE_INAT
        )
        self.dataset = Dataset.objects.create(
            gbif_dataset_key=INAT_DATASET_KEY, name="iNaturalist"
        )
        self.bor = BasisOfRecord.objects.create(name=INAT_BASIS_OF_RECORD)

    def test_basic_mapping(self):
        raw = make_inat_obs(obs_id=42, uuid="test-uuid-001", quality_grade="research")
        obs = build_observation_from_inat(raw, self.di, self.dataset, self.species, self.bor)

        self.assertIsNotNone(obs)
        self.assertEqual(obs.source, Observation.SOURCE_INAT)
        self.assertEqual(obs.inat_id, 42)
        self.assertEqual(obs.gbif_id, "")
        self.assertEqual(obs.occurrence_id, "test-uuid-001")
        self.assertEqual(obs.species, self.species)
        self.assertEqual(obs.date, datetime.date(2024, 6, 15))
        self.assertTrue(obs.verified)
        self.assertEqual(obs.identification_verification_status, "research")
        self.assertEqual(obs.recorded_by, "testuser")
        self.assertEqual(obs.locality, "Brussels")

    def test_needs_id_not_verified(self):
        raw = make_inat_obs(quality_grade="needs_id")
        obs = build_observation_from_inat(raw, self.di, self.dataset, self.species, self.bor)
        self.assertFalse(obs.verified)

    def test_obscured_has_no_location(self):
        raw = make_inat_obs(obscured=True)
        obs = build_observation_from_inat(raw, self.di, self.dataset, self.species, self.bor)
        self.assertIsNone(obs.location)

    def test_missing_date_returns_none(self):
        raw = make_inat_obs()
        raw["observed_on"] = None
        obs = build_observation_from_inat(raw, self.di, self.dataset, self.species, self.bor)
        self.assertIsNone(obs)

    def test_stable_id_is_set(self):
        raw = make_inat_obs(uuid="stable-uuid-test")
        obs = build_observation_from_inat(raw, self.di, self.dataset, self.species, self.bor)
        # stable_id should be deterministic: sha1("occ_id: stable-uuid-test d_id: inat")
        import hashlib
        expected = hashlib.sha1(
            b"occ_id: stable-uuid-test d_id: inat"
        ).hexdigest()
        self.assertEqual(obs.stable_id, expected)

    def test_observation_url_is_inat(self):
        raw = make_inat_obs(obs_id=99)
        obs = build_observation_from_inat(raw, self.di, self.dataset, self.species, self.bor)
        # observation_url is a property that needs source + inat_id set
        obs_saved = Observation(
            source=obs.source, inat_id=obs.inat_id, gbif_id=obs.gbif_id
        )
        self.assertEqual(
            obs_saved.observation_url,
            "https://www.inaturalist.org/observations/99",
        )


# ---------------------------------------------------------------------------
# import_inat_observations command tests
# ---------------------------------------------------------------------------


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    GBIF_ALERT=INAT_SETTINGS,
    ZOOM_LEVEL_FOR_MIN_MAX_QUERY=8,
)
class ImportInatObservationsCommandTest(TestCase):
    """
    Tests for the import_inat_observations management command.
    HTTP calls to iNat are mocked; PostGIS materialized views are also mocked.
    """

    def setUp(self):
        self.species = Species.objects.create(
            name="Vespa velutina", gbif_taxon_key=1311477, inat_taxon_id=119019
        )

    @patch("dashboard.management.commands.import_inat_observations.create_or_refresh_materialized_views")
    @patch("dashboard.inat_api.get_observations")
    def test_observations_are_created(self, mock_get_obs, mock_refresh):
        """Command creates Observation records from iNat API results."""
        mock_get_obs.return_value = iter([
            make_inat_obs(obs_id=1, uuid="uuid-001"),
            make_inat_obs(obs_id=2, uuid="uuid-002"),
        ])

        call_command("import_inat_observations")

        self.assertEqual(Observation.objects.filter(source=Observation.SOURCE_INAT).count(), 2)
        obs = Observation.objects.get(inat_id=1)
        self.assertEqual(obs.source, Observation.SOURCE_INAT)
        self.assertEqual(obs.occurrence_id, "uuid-001")

    @patch("dashboard.management.commands.import_inat_observations.create_or_refresh_materialized_views")
    @patch("dashboard.inat_api.get_observations")
    def test_inat_dataset_created(self, mock_get_obs, mock_refresh):
        """A single 'iNaturalist' Dataset record is created."""
        mock_get_obs.return_value = iter([make_inat_obs()])

        call_command("import_inat_observations")

        self.assertTrue(Dataset.objects.filter(gbif_dataset_key=INAT_DATASET_KEY).exists())

    @patch("dashboard.management.commands.import_inat_observations.create_or_refresh_materialized_views")
    @patch("dashboard.inat_api.get_observations")
    def test_previous_inat_obs_deleted(self, mock_get_obs, mock_refresh):
        """Previous iNat observations are replaced; GBIF observations survive."""
        # Create a pre-existing GBIF observation
        gbif_di = DataImport.objects.create(start=timezone.now(), source=DataImport.SOURCE_GBIF)
        gbif_dataset = Dataset.objects.create(gbif_dataset_key="gbif-key-001", name="GBIF dataset")
        bor, _ = BasisOfRecord.objects.get_or_create(name=INAT_BASIS_OF_RECORD)
        gbif_obs = Observation.objects.create(
            source=Observation.SOURCE_GBIF,
            gbif_id="GBIF-001",
            occurrence_id="gbif-occ-001",
            species=self.species,
            date=datetime.date(2024, 1, 1),
            data_import=gbif_di,
            initial_data_import=gbif_di,
            source_dataset=gbif_dataset,
            basis_of_record=bor,
        )

        mock_get_obs.return_value = iter([make_inat_obs(obs_id=10, uuid="inat-uuid-010")])

        call_command("import_inat_observations")

        # GBIF observation must still exist
        self.assertTrue(Observation.objects.filter(pk=gbif_obs.pk).exists())
        # New iNat observation must exist
        self.assertEqual(Observation.objects.filter(source=Observation.SOURCE_INAT).count(), 1)

    @patch("dashboard.management.commands.import_inat_observations.create_or_refresh_materialized_views")
    @patch("dashboard.inat_api.get_observations")
    def test_old_inat_obs_replaced_on_reimport(self, mock_get_obs, mock_refresh):
        """Running the command twice replaces the first iNat import with the second."""
        mock_get_obs.return_value = iter([make_inat_obs(obs_id=1, uuid="uuid-001")])
        call_command("import_inat_observations")
        self.assertEqual(Observation.objects.filter(source=Observation.SOURCE_INAT).count(), 1)

        # Second import with different data
        mock_get_obs.return_value = iter([
            make_inat_obs(obs_id=2, uuid="uuid-002"),
            make_inat_obs(obs_id=3, uuid="uuid-003"),
        ])
        call_command("import_inat_observations")

        self.assertEqual(Observation.objects.filter(source=Observation.SOURCE_INAT).count(), 2)
        self.assertFalse(Observation.objects.filter(inat_id=1).exists())

    @override_settings(
        GBIF_ALERT={**INAT_SETTINGS, "INAT_IMPORT_CONFIG": {**INAT_SETTINGS["INAT_IMPORT_CONFIG"], "ENABLED": False}}
    )
    def test_disabled_config_exits_early(self):
        """Command exits without importing when ENABLED=False."""
        call_command("import_inat_observations")
        self.assertEqual(Observation.objects.filter(source=Observation.SOURCE_INAT).count(), 0)

    def test_no_inat_taxon_ids_raises_error(self):
        """Command raises CommandError if no species have inat_taxon_id."""
        self.species.inat_taxon_id = None
        self.species.save()

        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("import_inat_observations")


# ---------------------------------------------------------------------------
# Observation model tests
# ---------------------------------------------------------------------------


class ObservationSourceTest(TestCase):
    """Tests for source-related Observation fields and properties."""

    def setUp(self):
        self.species = Species.objects.create(
            name="Vespa velutina", gbif_taxon_key=1311477
        )
        self.di = DataImport.objects.create(start=timezone.now())
        self.dataset = Dataset.objects.create(
            gbif_dataset_key="test-key", name="Test dataset"
        )
        self.bor = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")

    def _make_obs(self, **kwargs) -> Observation:
        defaults = dict(
            gbif_id="",
            occurrence_id="test-occ",
            species=self.species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.dataset,
            basis_of_record=self.bor,
        )
        defaults.update(kwargs)
        return Observation(**defaults)

    def test_gbif_observation_url(self):
        obs = self._make_obs(source=Observation.SOURCE_GBIF, gbif_id="12345")
        self.assertEqual(obs.observation_url, "https://www.gbif.org/occurrence/12345")

    def test_inat_observation_url(self):
        obs = self._make_obs(source=Observation.SOURCE_INAT, inat_id=67890)
        self.assertEqual(obs.observation_url, "https://www.inaturalist.org/observations/67890")

    def test_default_source_is_gbif(self):
        obs = self._make_obs()
        self.assertEqual(obs.source, Observation.SOURCE_GBIF)
