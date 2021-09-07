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
        json_data[0]["name"]
        json_data[0]["id"]
        json_data[0]["gbif_taxon_key"]

        # Check a specific one can be found
        found = False
        for entry in json_data:
            if entry["name"] == "Elodea nuttallii":
                found = True
                break

        self.assertTrue(found)


class VectorTilesServerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Occurrence.objects.create(gbif_id=1,
                                  species=Species.objects.all()[0],
                                  date=datetime.date.today(),
                                  location=Point(5.09513, 50.48941, srid=4326)  # Andenne
                                )
        Occurrence.objects.create(gbif_id=2,
                                  species=Species.objects.all()[0],
                                  date=datetime.date.today(),
                                  location=Point(4.35978, 50.64728, srid=4326)  # Lillois
                                  )

    def test_base_mvt_server(self):
        """There's a tile server returning the appropriate MIME type"""
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 1, "x": 1, "y": 1})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Type"], "application/vnd.mapbox-vector-tile"
        )

    def test_basic_data_in_hexagons(self):
        # Very large view (big part of Europe, Africa and Russia: e expect a single hexagon over Belgium
        #
        # Those tests can be more easily debugged with a "TileDebug" layer in OpenLayers:
        # https://openlayers.org/en/latest/examples/canvas-tiles.html
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 2, "x": 2, "y": 1})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)

        self.assertEqual(len(decoded_tile['default']['features']), 1)  # it has a single feature
        the_feature = decoded_tile['default']['features'][0]
        self.assertEqual(the_feature['properties']['count'], 2)  # It has a "count" property with the value 2
        self.assertEqual(the_feature['geometry']['type'], 'Polygon')  # the feature is a polygon
        self.assertEqual(len(the_feature['geometry']['coordinates'][0]), 7)  # 7 coordinates pair = 6 sides

        # Another very large tile, over Groenland. Should be empty
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 2, "x": 1, "y": 0})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # A tile that covers an important part of Wallonia, including Andenne and Braine. Should have two polygons
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 8, "x": 131, "y": 86})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile['default']['features']), 2)  # it has two features

        self.assertEqual(decoded_tile['default']['features'][0]['properties']['count'], 1)
        self.assertEqual(decoded_tile['default']['features'][1]['properties']['count'], 1)

        # The tile east of it should be empty
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 8, "x": 132, "y": 86})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # A tile with just Andenne and the close neighborhood
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 10, "x": 526, "y": 345})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile['default']['features']), 1)  # it has a single feature
        self.assertEqual(decoded_tile['default']['features'][0]['properties']['count'], 1)

        # The one on the west is empty
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 10, "x": 525, "y": 345})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

        # Let's get a very small tile containing the Lillois occurrence
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 17, "x": 67123, "y": 44083})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(len(decoded_tile['default']['features']), 1)  # it has a single feature
        self.assertEqual(decoded_tile['default']['features'][0]['properties']['count'], 1)

        # The next one is empty
        response = self.client.get(
            reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated", kwargs={"zoom": 17, "x": 67124, "y": 44083})
        )
        decoded_tile = mapbox_vector_tile.decode(response.content)
        self.assertEqual(decoded_tile, {})

    def test_zoom_levels(self):
        """Zoom levels 1-20 are supported"""
        for zoom_level in range(1,21):
            response = self.client.get(
                reverse("dashboard:api-mvt-tiles-hexagon-grid-aggregated",
                        kwargs={"zoom": zoom_level, "x": 1, "y": 1})
            )
            self.assertEqual(response.status_code, 200)
            mapbox_vector_tile.decode(response.content)

