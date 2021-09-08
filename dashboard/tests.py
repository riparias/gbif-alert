import datetime

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

import mapbox_vector_tile

from dashboard.models import Occurrence, Species


class WebPagesTests(TestCase):
    def test_homepage(self):
        """There's a Bootstrap-powered page at /"""
        response = self.client.get("/")
        self.assertContains(response, "bootstrap.min.css", status_code=200)
        self.assertContains(response, "container")
        self.assertTemplateUsed(response, "dashboard/index.html")


class ApiTests(TestCase):
    def test_species_list_json(self):
        response = self.client.get(reverse("dashboard:api-species-list-json"))
        self.assertEqual(response.status_code, 200)
        # There's already 18 entries in the species table thanks to a data migration (0002_populate_initial_species.py)

        json_data = response.json()
        self.assertEqual(len(json_data), 18)

        # Check the main fields are there (no KeyError exception)
        json_data[0]["scientificName"]
        json_data[0]["id"]
        json_data[0]["gbifTaxonKey"]

        # Check a specific one can be found
        found = False
        for entry in json_data:
            if entry["scientificName"] == "Elodea nuttallii":
                found = True
                break

        self.assertTrue(found)


class VectorTilesServerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.first_species = Species.objects.all()[0]
        cls.second_species = Species.objects.all()[1]

        Occurrence.objects.create(
            gbif_id=1,
            species=cls.first_species,
            date=datetime.date.today(),
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )
        Occurrence.objects.create(
            gbif_id=2,
            species=cls.second_species,
            date=datetime.date.today(),
            location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        )

    def test_base_mvt_server(self):
        """There's a tile server returning the appropriate MIME type"""
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 1, "x": 1, "y": 1},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Type"], "application/vnd.mapbox-vector-tile"
        )

    def test_tiles_null_filters_ignored(self):
        """Regression test: filters at null in the URL don't create problems, the filter is just ignored.

        Derived from test_basic_data_in_hexagons()
        """
        base_url = reverse(
            "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = f"{base_url}?speciesId=null&startDate=null&endDate=null"
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)

        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 2
        )  # It has a "count" property with the value 2

    def test_tiles_species_filter(self):
        # Multiple cases where only the occurrence in Andenne is visible

        # Case 1: Large-scale view: a single he over Wallonia, but count = 1
        base_url = reverse(
            "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
        url_with_params = (
            f"{base_url}?speciesId={VectorTilesServerTests.first_species.pk}"
        )
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        the_feature = decoded_tile["default"]["features"][0]
        self.assertEqual(
            the_feature["properties"]["count"], 1
        )  # Only one occurrence this time, due to the filter

        # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
        # polygon this time
        base_url = reverse(
            "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
            kwargs={"zoom": 8, "x": 131, "y": 86},
        )
        url_with_params = (
            f"{base_url}?speciesId={VectorTilesServerTests.first_species.pk}"
        )
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
            "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
        url_with_params = (
            f"{base_url}?speciesId={VectorTilesServerTests.first_species.pk}"
        )
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
            "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
            kwargs={"zoom": 17, "x": 67123, "y": 44083},
        )
        url_with_params = (
            f"{base_url}?speciesId={VectorTilesServerTests.first_species.pk}"
        )
        response = self.client.get(url_with_params)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_tiles_basic_data_in_hexagons(self):
        # Very large view (big part of Europe, Africa and Russia: e expect a single hexagon over Belgium
        #
        # Those tests can be more easily debugged with a "TileDebug" layer in OpenLayers:
        # https://openlayers.org/en/latest/examples/canvas-tiles.html
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
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

        # Another very large tile, over Groenland. Should be empty
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 2, "x": 1, "y": 0},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # A tile that covers an important part of Wallonia, including Andenne and Braine. Should have two polygons
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
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
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 8, "x": 132, "y": 86},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # A tile with just Andenne and the close neighborhood
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
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
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 10, "x": 525, "y": 345},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Let's get a very small tile containing the Lillois occurrence
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 17, "x": 67123, "y": 44083},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(
            len(decoded_tile["default"]["features"]), 1
        )  # it has a single feature
        self.assertEqual(
            decoded_tile["default"]["features"][0]["properties"]["count"], 1
        )

        # The next one is empty
        response = self.client.get(
            reverse(
                "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                kwargs={"zoom": 17, "x": 67124, "y": 44083},
            )
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_zoom_levels(self):
        """Zoom levels 1-20 are supported"""
        for zoom_level in range(1, 21):
            response = self.client.get(
                reverse(
                    "dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                    kwargs={"zoom": zoom_level, "x": 1, "y": 1},
                )
            )
            self.assertEqual(response.status_code, 200)
            mapbox_vector_tile.decode(response.content)

    def test_min_max_per_hexagon(self):
        # At zoom level 8, with the initial data: we should have two polygons, both at 1. So min=1 and max=1
        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"), data={"zoom": 8}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Add a second one in Lillois, but not next to the other one
        Occurrence.objects.create(
            gbif_id=3,
            species=Species.objects.all()[0],
            date=datetime.date.today(),
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        )

        # Now, at zoom level 8 we should have an hexagon with count=1 and another one with count=2
        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"), data={"zoom": 8}
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)

        # But at a very large scale, one single hexagon with count=3
        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"), data={"zoom": 1}
        )
        self.assertEqual(response.json()["min"], 3)
        self.assertEqual(response.json()["max"], 3)

        # At zoom level 17, there's no hexagons that cover more than 1 occurrence
        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"), data={"zoom": 17}
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

    def test_min_max_per_hexagon_with_species_filter(self):
        # Add a second one in Lillois, but not next to the other one and another species
        Occurrence.objects.create(
            gbif_id=3,
            species=VectorTilesServerTests.second_species,
            date=datetime.date.today(),
            location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        )

        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"),
            data={"zoom": 8, "speciesId": VectorTilesServerTests.first_species.pk},
        )
        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 1)

        # Now we're looking for the second species. (We have 2 in Lillois and none in Andenne)
        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"),
            data={"zoom": 8, "speciesId": VectorTilesServerTests.second_species.pk},
        )

        self.assertEqual(response.json()["min"], 2)
        self.assertEqual(response.json()["max"], 2)

        # Now let's add another one in Andenne for species 2: whe should now have 1,2
        Occurrence.objects.create(
            gbif_id=4,
            species=VectorTilesServerTests.second_species,
            date=datetime.date.today(),
            location=Point(5.095610, 50.48800, srid=4326),
        )

        response = self.client.get(
            reverse("dashboard:api-mvt-min-max-per-hexagon"),
            data={"zoom": 8, "speciesId": VectorTilesServerTests.second_species.pk},
        )

        self.assertEqual(response.json()["min"], 1)
        self.assertEqual(response.json()["max"], 2)
