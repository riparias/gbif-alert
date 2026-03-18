import datetime

import mapbox_vector_tile
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dashboard.models import (
    BasisOfRecord,
    Observation,
    Species,
    DataImport,
    Dataset,
    Area,
    ObservationUnseen,
)
from dashboard.views.helpers import (
    create_or_refresh_all_materialized_views,
    create_or_refresh_materialized_views,
)


class MapsTestDataMixin(object):
    """Multiple test cases share some test data via this mixin"""

    @classmethod
    def setUpTestData(cls):
        cls.basis_of_record = BasisOfRecord.objects.create(
            name="HUMAN_OBSERVATION"
        )

        cls.first_species = Species.objects.create(
            name="Procambarus fallax", gbif_taxon_key=8879526
        )
        cls.second_species = Species.objects.create(
            name="Orconectes virilis", gbif_taxon_key=2227064
        )

        cls.di = DataImport.objects.create(start=timezone.now())
        cls.first_dataset = Dataset.objects.create(
            name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        )
        cls.second_dataset = Dataset.objects.create(
            name="Test dataset #2",
            gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
        )

        obs = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=cls.first_species,
            date=datetime.date(2020, 1, 1),
            data_import=cls.di,
            initial_data_import=cls.di,
            source_dataset=cls.first_dataset,
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
            basis_of_record=cls.basis_of_record,
        )
        Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            species=cls.second_species,
            date=datetime.date.today(),
            data_import=cls.di,
            initial_data_import=cls.di,
            source_dataset=cls.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
            basis_of_record=cls.basis_of_record,
        )

        cls.public_area_andenne = Area.objects.create(
            name="Public polygon - Andenne",
            # Covers Namur-Liège area (includes Andenne but not Lillois)
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (4.7866, 50.5200),
                        (5.6271, 50.6839),
                        (5.6930, 50.5724),
                        (4.8306, 50.4116),
                        (4.7866, 50.5200),
                    ),
                    srid=4326,
                ),
                srid=4326,
            ),
        )

        cls.public_area_lillois = Area.objects.create(
            name="Public polygon - Lillois",
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (4.3164, 50.6658),
                        (4.4025, 50.6658),
                        (4.4025, 50.6164),
                        (4.3164, 50.6164),
                        (4.3164, 50.6658),
                    ),
                    srid=4326,
                ),
                srid=4326,
            ),
        )

        User = get_user_model()
        cls.user = User.objects.create_user(
            username="frusciante",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        ObservationUnseen.objects.create(observation=obs, user=cls.user)

        create_or_refresh_all_materialized_views()


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class MinMaxPerHexagonTests(MapsTestDataMixin, TestCase):
    """Tests covering the min_max_in_hexagon endpoint"""

    def test_min_max_status_area_combinations(self):
        """Regression test for https://github.com/riparias/gbif-alert/issues/283"""
        self.client.login(username="frusciante", password="12345")

        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "status": "seen",
                "areaIds[]": self.public_area_andenne.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_min_max_per_hexagon(self):
        # At zoom level 8, with the initial data: we should have two polygons, both at 1. So min=1 and max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Add a second one in Lillois, but not next to the other one
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=Species.objects.all()[0],
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8, 1, 13])

        # Now, at zoom level 8 we should have a hexagon with count=1 and another one with count=2
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

        # But at a very large scale, one single hexagon with count=3
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 1},
        )
        self.assertEqual(response.json()["min"], 3)
        self.assertEqual(response.json()["max"], 3)

        # At zoom level 17, there's no hexagons that cover more than 1 observation
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 13},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

    def test_min_max_per_hexagon_with_species_filter(self):
        # Add a second one in Lillois, but not next to the other one and another species
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3LKDVC",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "speciesIds[]": self.first_species.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Now we're looking for the second species. (We have 2 in Lillois and none in Andenne)
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "speciesIds[]": [self.second_species.pk],
            },
        )

        self.assertEqual(response.json()["min"], 2)
        self.assertEqual(response.json()["max"], 2)

        # Now let's add another one in Andenne for species 2: whe should now have 1,2
        Observation.objects.create(
            gbif_id=4,
            occurrence_id="4",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(5.095610, 50.48800, srid=4326),
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "speciesIds[]": self.second_species.pk},
        )

        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_dataset_filter(self):
        # Add a second one in Lillois, but not next to the other one and another species
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3DSRZER",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "datasetsIds[]": self.first_dataset.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Now we're looking for the second species. (We have 2 in Lillois and none in Andenne)
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "speciesIds[]": [self.second_species.pk],
            },
        )

        self.assertEqual(response.json()["min"], 2)
        self.assertEqual(response.json()["max"], 2)

        # Now let's add another one in Andenne for species 2: whe should now have 1,2
        Observation.objects.create(
            gbif_id=4,
            occurrence_id="4",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(5.095610, 50.48800, srid=4326),
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "speciesIds[]": self.second_species.pk},
        )

        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_basis_of_record_filter(self):
        second_bor = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
        # Add a third observation at the same location as obs2 (Lillois) with a different basis of record
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3BOR",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
            basis_of_record=second_bor,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # Filter by HUMAN_OBSERVATION: Andenne=1, Lillois=1 -> min=1, max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "basisOfRecordIds[]": self.basis_of_record.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Filter by MACHINE_OBSERVATION: only Lillois=1 -> min=1, max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "basisOfRecordIds[]": second_bor.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Without filter: Andenne=1, Lillois=2 -> min=1, max=2
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_verified_filter(self):
        # Add a third observation at Lillois with verified=True (obs1 and obs2 are unverified by default)
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3VER",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
            basis_of_record=self.basis_of_record,
            verified=True,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # Filter for verified only: only obs3 in Lillois -> min=1, max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "verifiedFilter": "verified"},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Filter for unverified only: obs1 in Andenne + obs2 in Lillois -> min=1, max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "verifiedFilter": "unverified"},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Without filter: Andenne=1, Lillois=2 -> min=1, max=2
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_in_hexagon_with_status_filter_invalid_value(self):
        """status is not seen nor unseen, therefore is ignored and everything is included"""
        self.client.login(username="frusciante", password="12345")
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 1, "status": "all"},
        )
        self.assertEqual(response.json()["min"], 2)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_in_hexagon_with_status_filter(self):
        # Add a second one in Lillois, but not next to the other
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
            basis_of_record=self.basis_of_record,
        )

        self.client.login(username="frusciante", password="12345")

        # At a zoom level that only shows Lillois or Andenne, it's 1-1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "status": "unseen",
            },
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

    def test_min_max_in_hexagon_with_status_filter_anonymous(self):
        """Similar to test_min_max_in_hexagon_with_status_filter(), but anonymous -> filters get ignored"""
        # Add a second one in Lillois, but not next to the other
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # At a zoom level that only shows Lillois or Andenne, it's 1-1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "status": "unseen",
            },
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_area_filter(self):
        # Add a second one in Lillois, but not next to the other
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # We restrict ourselves to Andenne: only one observation
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "areaIds[]": self.public_area_andenne.pk,
            },
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Case 2: we limit ourselves to Lillois (one single hexagon, with count=2)
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "areaIds[]": self.public_area_lillois.pk,
            },
        )
        self.assertEqual(response.json()["min"], 2)
        self.assertEqual(response.json()["max"], 2)

        # Case3: Test with multiple areas: we request both Andenne and Lillois: same results as no filters
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={
                "zoom": 8,
                "areaIds[]": [
                    self.public_area_lillois.pk,
                    self.public_area_andenne.pk,
                ],
            },
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_initial_data_import_filter(self):
        second_di = DataImport.objects.create(start=timezone.now())
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.first_species,
            date=datetime.date.today(),
            data_import=second_di,
            initial_data_import=second_di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # Filter by first data import: 2 observations in different hexagons -> min=1, max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "initialDataImportIds[]": self.di.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Filter by second data import: 1 observation -> min=1, max=1
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "initialDataImportIds[]": second_di.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Without filter: Andenne has 1, Lillois has 2 -> min=1, max=2
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_start_date_filter(self):
        # Add a third observation in Lillois with a recent date
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.first_species,
            date=datetime.date(2023, 6, 15),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # Without filter: Andenne has 1 obs, Lillois has 2 -> min=1, max=2
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

        # With startDate=2022-01-01: obs1 (2020-01-01) excluded, obs2 (today) and obs3 (2023-06-15) remain in Lillois
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "startDate": "2022-01-01"},
        )
        self.assertEqual(response.json()["min"], 2)
        self.assertEqual(response.json()["max"], 2)

    def test_min_max_per_hexagon_with_end_date_filter(self):
        # Add a third observation in Lillois with a recent date
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.first_species,
            date=datetime.date(2023, 6, 15),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )

        create_or_refresh_materialized_views(zoom_levels=[8])

        # With endDate=2022-02-02: only obs1 (2020-01-01) in Andenne remains
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
            data={"zoom": 8, "endDate": "2022-02-02"},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

    def test_min_max_per_hexagon_no_zoom(self):
        """When zoom is not provided, the view returns a 400 error"""
        response = self.client.get(
            reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        )
        self.assertEqual(response.status_code, 400)


class MVTServerCommonTestsMixin(object):
    """Common tests to be mixed in any MVT server test class

    The following attributes should be present in the "mixing in" classes:

    - server_url_name
    """

    server_url_name = ""  # To be configured in classes that use this mixin

    def _build_valid_tile_url(self, zoom: int) -> str:
        return reverse(
            self.server_url_name,
            # X and Y are at zero, so it works at all zoom levels (zoom level 0: a single tile for the whole world)
            kwargs={"zoom": zoom, "x": 0, "y": 0},
        )

    def test_status_and_content_type(self):
        """The server responds with the correct status code and content-type"""
        response = self.client.get(self._build_valid_tile_url(zoom=1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Type"], "application/vnd.mapbox-vector-tile"
        )

    def test_zoom_levels(self):
        """Zoom levels 0-14 are supported"""
        for zoom_level in range(0, 14):
            response = self.client.get(self._build_valid_tile_url(zoom=zoom_level))
            self.assertEqual(response.status_code, 200)
            mapbox_vector_tile.decode(response.content)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class MVTServerSingleObsTests(MapsTestDataMixin, MVTServerCommonTestsMixin, TestCase):
    """Tests covering the MVT server (tiles generation) for non-aggregated observations"""

    server_url_name = "dashboard:internal-api:maps:mvt-tiles"

    def test_tiles_features_type(self):
        """The server return points"""
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 2, "x": 2, "y": 1},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        for feature in decoded_tile["default"]["features"]:
            self.assertEqual(feature["geometry"]["type"], "Point")

    def test_tiles_no_filter(self):
        # Case 1: A large view over Wallonia
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 2, "x": 2, "y": 1},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        # 2 points are present
        self.assertEqual(len(decoded_tile["default"]["features"]), 2)
        for feature in decoded_tile["default"]["features"]:
            self.assertIn(feature["properties"]["gbif_id"], ["1", "2"])

        # Case 2: Zoom to Andenne
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 10, "x": 526, "y": 345},
            )
        )

        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

    def test_tiles_area_filter(self):
        # Case 1: A large view over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        url_with_params = f"{base_url}?areaIds[]={self.public_area_andenne.pk}"

        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        # only one point is present because of the area filtering
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

        # Case 2: Zoom to Andenne, the point there shouldn't be impacted by the filtering
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?areaIds[]={self.public_area_andenne.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)

        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

    def test_tiles_dataset_filter(self):
        # Case 1: A large view over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        url_with_params = f"{base_url}?datasetsIds[]={self.second_dataset.pk}"

        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        # only one point is present because of the dataset filtering
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "2"
        )

        # Case 2: Zoom to Andenne, there should be no observation because of the filtering
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?datasetsIds[]={self.second_dataset.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Case 3: Zoom to Lillois, the obs should be seen again
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 17, "x": 67123, "y": 44083},
        )
        url_with_params = f"{base_url}?datasetsIds[]={self.second_dataset.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "2"
        )

    def test_tiles_basis_of_record_filter(self):
        second_bor = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
        # Add a third observation at the same location as obs2 (Lillois) with a different basis of record
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3BOR",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
            basis_of_record=second_bor,
        )

        # Case 1: A large view over Wallonia, filter by MACHINE_OBSERVATION
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        # Only the new observation should be present
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "3"
        )

        # Case 2: Zoom to Andenne, filter by MACHINE_OBSERVATION: no observation
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Case 3: Zoom to Lillois, filter by MACHINE_OBSERVATION: obs3 visible
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 17, "x": 67123, "y": 44083},
        )
        url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "3"
        )

    def test_tiles_verified_filter(self):
        # Add a third observation at Lillois with verified=True (obs1 and obs2 are unverified by default)
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3VER",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
            basis_of_record=self.basis_of_record,
            verified=True,
        )

        # Case 1: Large view over Wallonia, filter by verified: only obs3
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?verifiedFilter=verified"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "3"
        )

        # Case 2: Filter by unverified: obs1 and obs2 only (2 features)
        url_with_params = f"{base_url}?verifiedFilter=unverified"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 2)
        gbif_ids = {f["properties"]["gbif_id"] for f in decoded_tile["default"]["features"]}
        self.assertEqual(gbif_ids, {"1", "2"})

        # Case 3: Zoom to Andenne, filter by verified: no obs (obs1 in Andenne is unverified)
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?verifiedFilter=verified"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_start_date_filter(self):
        """Use the startDate parameter to filter out observations that are too old"""
        # Case 1: A large view over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        url_with_params = f"{base_url}?startDate=2022-01-01"

        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        # only one point is present because of the date filtering
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        # It's the one in Lillois
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "2"
        )

        # Case 2: Zoom to Andenne, there should be no observation because of the filtering
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?startDate=2022-01-01"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Case 3: Zoom to Lillois, the obs should be seen again
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 17, "x": 67123, "y": 44083},
        )
        url_with_params = f"{base_url}?startDate=2022-01-01"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "2"
        )

    def test_tiles_end_date_filter(self):
        """Use the endDate parameter to filter out observations that are too recent"""
        # Case 1: A large view over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        url_with_params = f"{base_url}?endDate=2022-02-02"

        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        # only one point is present because of the date filtering
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        # It's the one in Andenne
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

        # Case 2: Zoom to Andenne, there should be one observation
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?endDate=2022-02-02"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

        # Case 3: Zoom to Lillois, there should be no obs
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 17, "x": 67123, "y": 44083},
        )
        url_with_params = f"{base_url}?endDate=2022-02-02"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_combined_filters(self):
        # Test a combination of filters per status (seen/unseen) and species
        self.client.login(username="frusciante", password="12345")

        # Case 1: Large-scale view: a single hex over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        # First, all seen observations for the user => only the one in Lillois
        url_with_params = f"{base_url}?status=seen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "2"
        )

        # All unseen observations => only the one in Andenne
        url_with_params = f"{base_url}?status=unseen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

        # Same, but we add some species filtering that doesn't filter anything out
        url_with_params = (
            f"{base_url}?status=unseen&speciesIds[]={self.first_species.pk}"
        )
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "1"
        )

        # Finally, we remove the observation by applying another species filter
        url_with_params = (
            f"{base_url}?status=unseen&speciesIds[]={self.second_species.pk}"
        )
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_initial_data_import_filter(self):
        second_di = DataImport.objects.create(start=timezone.now())
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.first_species,
            date=datetime.date.today(),
            data_import=second_di,
            initial_data_import=second_di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )

        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        # Filter by first data import: only the 2 original observations
        url_with_params = f"{base_url}?initialDataImportIds[]={self.di.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 2)

        # Filter by second data import: only the new observation
        url_with_params = f"{base_url}?initialDataImportIds[]={second_di.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["gbif_id"], "3"
        )

    def test_tiles_vernacular_name_in_active_language(self):
        """Tile properties include the vernacular name for the active language."""
        tile_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        self.first_species.vernacular_name_en = "Marbled crayfish"
        self.first_species.vernacular_name_nl = "Marmerkreeft"
        self.first_species.vernacular_name_fr = "Ecrevisse marbre"
        self.first_species.save()

        # The language selector sets a django_language cookie; simulate that here.
        # (The browser's Accept-Language header is always en-US regardless of the UI language.)
        for lang_code, expected_name in [
            ("en", "Marbled crayfish"),
            ("nl", "Marmerkreeft"),
            ("fr", "Ecrevisse marbre"),
        ]:
            self.client.cookies["django_language"] = lang_code
            response = self.client.get(tile_url)
            decoded_tile = mapbox_vector_tile.decode(response.content)
            features_by_gbif_id = {
                f["properties"]["gbif_id"]: f
                for f in decoded_tile["default"]["features"]
            }
            self.assertEqual(
                features_by_gbif_id["1"]["properties"]["vernacular_name"],
                expected_name,
                msg=f"Wrong vernacular name for language '{lang_code}'",
            )

        # A species with no vernacular name should have no vernacular_name property in the tile
        self.assertNotIn(
            "vernacular_name",
            features_by_gbif_id["2"]["properties"],
        )


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class MVTServerAggregatedObsTests(
    MapsTestDataMixin, MVTServerCommonTestsMixin, TestCase
):
    """Tests covering the MVT server (tiles generation) for hexagon-aggregated observations"""

    server_url_name = "dashboard:internal-api:maps:mvt-tiles-hexagon-grid-aggregated"

    def test_tiles_features_type(self):
        """The server return 6-sided polygons"""
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 2, "x": 2, "y": 1},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        for feature in decoded_tile["default"]["features"]:
            self.assertEqual(feature["geometry"]["type"], "Polygon")
            self.assertEqual(
                len(feature["geometry"]["coordinates"][0]), 7
            )  # 7 coordinates pair = 6 sides

    def test_tiles_null_filters_ignored(self):
        """Regression test: filters at null in the URL don't create problems, the filter is just ignored.

        Derived from test_basic_data_in_hexagons()
        """
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?startDate=null&endDate=null"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)

        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 2
        )  # It has a "count" property with the value 2

    def test_tiles_area_filter(self):
        # We explore tiles at different zoom levels. In all cases the observation in Lillois should be filtered out by
        # the areaId filtering.

        # Case 1: large view over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},  # Large views over Wallonia
        )
        url_with_params = f"{base_url}?areaIds[]={self.public_area_andenne.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)

        # We have one single hexagon (because of the zoom level), its counter is 1 (because Lillois observation was filtered out)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(the_feature["properties"]["count"], 1)

        # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
        # hexagon (because of the area filtering)
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 8, "x": 131, "y": 86},
        )
        url_with_params = f"{base_url}?areaIds[]={self.public_area_andenne.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?areaIds[]={self.public_area_andenne.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 4: A zoomed time on Lillois, should be empty because of the filtering
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?areaIds[]={self.public_area_andenne.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_status_filter_anonymous(self):
        """Similar to test_tiles_status_filter_case1() but anonymous => filter is ignored"""
        # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?status=seen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(the_feature["properties"]["count"], 2)

    def test_tiles_status_filter_invalid_filter_value(self):
        """Similar to test_tiles_status_filter_case1() but with a filter that's not seen | unseen => filter is ignored
        and everything is included"""
        # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
        self.client.login(username="frusciante", password="12345")
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?status=all"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(the_feature["properties"]["count"], 2)

    def test_tiles_status_filter_case1(self):
        self.client.login(username="frusciante", password="12345")
        # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?status=seen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 1
        )  # Only one observation this time, due to the filter

    def test_tiles_status_filter_case2(self):
        self.client.login(username="frusciante", password="12345")
        # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?status=unseen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)

        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 1
        )  # Only one observation this time (the one in Andenne), due to the filter

        # Case 2: zoom a bit to make sure it's the one in Andenne

        # Case 2.1: it still appears when zoomed on Andenne
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?status=unseen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 2.2: there's nothing when zoomed on Lillois
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?status=unseen"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_species_filter(self):
        # We explore tiles at different zoom levels. In all cases the observation in Lillois should be filtered out by
        # the speciesId filtering.
        # Multiple cases where only the observation in Andenne is visible

        # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 1
        )  # Only one observation this time, due to the filter

        # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
        # polygon this time
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 8, "x": 131, "y": 86},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 4: A zoomed time on Lillois, should be empty because of the filtering
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_multiple_dataset_filters(self):
        """Explicitely requesting all datasets give the same results as no filtering"""
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?&datasetsIds[]={self.first_dataset.pk}&datasetsIds[]={self.second_dataset.pk}"
        response = self.client.get(url_with_params)
        decoded_tile_explicit_filters = mapbox_vector_tile.decode(response.content)

        response = self.client.get(base_url)
        decoded_tile_no_filters = mapbox_vector_tile.decode(response.content)

        self.assertEqual(decoded_tile_no_filters, decoded_tile_explicit_filters)

    def test_tiles_dataset_filter(self):
        # Inspired by test_tiles_species_filter

        # Multiple cases where only the observation in Andenne is visible
        # (because we only ask for the first dataset)

        # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?&datasetsIds[]={self.first_dataset.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 1
        )  # Only one observation this time, due to the filter

        # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
        # polygon this time
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 8, "x": 131, "y": 86},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 4: A zoomed time on Lillois, should be empty because of the filtering
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_basis_of_record_filter(self):
        second_bor = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
        # Add a third observation at the same location as obs2 (Lillois) with a different basis of record
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3BOR",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
            basis_of_record=second_bor,
        )

        # Case 1: Large-scale view: a single hex over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        # Filter by HUMAN_OBSERVATION: count should be 2 (obs1 + obs2)
        url_with_params = f"{base_url}?basisOfRecordIds[]={self.basis_of_record.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 2
        )

        # Filter by MACHINE_OBSERVATION: count should be 1 (only obs3 in Lillois)
        url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 2: Zoom on Andenne, filter by MACHINE_OBSERVATION: should be empty
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Case 3: Zoom on Lillois, filter by MACHINE_OBSERVATION: count=1
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

    def test_tiles_verified_filter(self):
        # Add a third observation at Lillois with verified=True (obs1 and obs2 are unverified by default)
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3VER",
            species=self.second_species,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.second_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
            basis_of_record=self.basis_of_record,
            verified=True,
        )

        # Case 1: Large-scale view over Wallonia (single hex)
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        # Filter by verified: count should be 1 (only obs3)
        url_with_params = f"{base_url}?verifiedFilter=verified"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Filter by unverified: count should be 2 (obs1 + obs2)
        url_with_params = f"{base_url}?verifiedFilter=unverified"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 2
        )

        # Case 2: Zoom on Andenne, filter by verified: should be empty (obs1 is unverified)
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?verifiedFilter=verified"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_species_multiple_species_filters(self):
        # Test based on test_tiles_species_filter(self), but with two species explicitly requested

        # We need first to add a new species and related observations:
        species_tetraodon = Species.objects.create(
            name="Tetraodon fluviatilis", gbif_taxon_key=5213564
        )
        Observation.objects.create(
            gbif_id=1000,
            occurrence_id="1000",
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )
        Observation.objects.create(
            gbif_id=1001,
            occurrence_id="1001",
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )
        Observation.objects.create(
            gbif_id=1002,
            occurrence_id="1002",
            species=species_tetraodon,
            date=datetime.date.today(),
            data_import=self.di,
            initial_data_import=self.di,
            source_dataset=self.first_dataset,
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )

        # Case 1: Large-scale view: a single hex over Wallonia
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}&speciesIds[]={species_tetraodon.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 4
        )  # 3 in Lillois (tetraodon, 1 in Andenne)

        # Case 2: A tile that covers an important part of Wallonia, including Andenne and Lillois. Should have two polygons
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 8, "x": 131, "y": 86},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}&speciesIds[]={species_tetraodon.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 2)

        # We should have one observation in Andenne (for first species) and 3 in Lillois (for tetraodon)
        pass
        for entry in decoded_tile["default"]["features"]:
            self.assertIn(entry["properties"]["count"], [1, 3])

        # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}&speciesIds[]={species_tetraodon.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Case 4: A zoomed time on Lillois, we expect the three tetraodon observations
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?speciesIds[]={self.first_species.pk}&speciesIds[]={species_tetraodon.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 3
        )

    def test_tiles_basic_data_in_hexagons(self):
        # Very large view (big part of Europe, Africa and Russia: e expect a single hexagon over Belgium
        #
        # Those tests can be more easily debugged with a "TileDebug" layer in OpenLayers:
        # https://openlayers.org/en/latest/examples/canvas-tiles.html
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 2, "x": 2, "y": 1},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)

        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 2
        )  # It has a "count" property with the value 2
        self.assertEqual(
            the_feature["geometry"]["type"], "Polygon"
        )  # the feature is a polygon
        self.assertEqual(
            len(the_feature["geometry"]["coordinates"][0]), 7
        )  # 7 coordinates pair = 6 sides

        # Another very large tile, over Greenland. Should be empty
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 2, "x": 1, "y": 0},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # A tile that covers an important part of Wallonia, including Andenne and Braine. Should have two polygons
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 8, "x": 131, "y": 86},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 2
        )  # it has two features

        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )
        self.assertEqual(
            decoded_tile["default"]["features"][1]["properties"]["count"], 1
        )

        # The tile east of it should be empty
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 8, "x": 132, "y": 86},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # A tile with just Andenne and the close neighborhood
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 10, "x": 526, "y": 345},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # The one on the west is empty
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 10, "x": 525, "y": 345},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Let's get a very small tile containing the Lillois observations
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 14, "x": 8390, "y": 5510},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # The next tile is empty
        response = self.client.get(
            reverse(
                self.server_url_name,
                kwargs={"zoom": 14, "x": 8391, "y": 5510},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_initial_data_import_filter(self):
        second_di = DataImport.objects.create(start=timezone.now())
        Observation.objects.create(
            gbif_id=3,
            occurrence_id="3",
            species=self.first_species,
            date=datetime.date.today(),
            data_import=second_di,
            initial_data_import=second_di,
            source_dataset=self.first_dataset,
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois
            basis_of_record=self.basis_of_record,
        )

        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        # Filter by first data import: one hexagon with count=2
        url_with_params = f"{base_url}?initialDataImportIds[]={self.di.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 2
        )

        # Filter by second data import: one hexagon with count=1
        url_with_params = f"{base_url}?initialDataImportIds[]={second_di.pk}"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

    def test_tiles_start_date_filter(self):
        """Use the startDate parameter to filter out old observations"""
        # At zoom 2: both observations are in one hexagon.
        # obs1 is 2020-01-01 (Andenne), obs2 is today (Lillois).
        # startDate=2022-01-01 should exclude obs1, leaving count=1.
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        url_with_params = f"{base_url}?startDate=2022-01-01"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Zoomed on Andenne: should be empty because the old observation is filtered out
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = f"{base_url}?startDate=2022-01-01"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_end_date_filter(self):
        """Use the endDate parameter to filter out recent observations"""
        # endDate=2022-02-02 should exclude obs2 (today), leaving only obs1 (2020-01-01).
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )

        url_with_params = f"{base_url}?endDate=2022-02-02"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile["default"]["features"]), 1)
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # Zoomed on Lillois: should be empty because the recent observation is filtered out
        base_url = reverse(
            self.server_url_name,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
        url_with_params = f"{base_url}?endDate=2022-02-02"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})
