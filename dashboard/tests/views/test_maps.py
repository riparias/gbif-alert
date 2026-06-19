import datetime

import mapbox_vector_tile
import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse
from django.utils import timezone

from dashboard.models import (
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationUnseen,
    Species,
)
from dashboard.views.helpers import (
    create_or_refresh_all_materialized_views,
    create_or_refresh_materialized_views,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def maps_data():
    """Shared data for all map tests (replaces MapsTestDataMixin.setUpTestData)."""
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    first_species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    second_species = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
    di = DataImport.objects.create(start=timezone.now())
    first_dataset = Dataset.objects.create(
        name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
    )
    second_dataset = Dataset.objects.create(
        name="Test dataset #2", gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
    )
    obs = Observation.objects.create(
        gbif_id=1, occurrence_id="1", species=first_species,
        date=datetime.date(2020, 1, 1), data_import=di, initial_data_import=di,
        source_dataset=first_dataset, location=Point(5.09513, 50.48941, srid=4326),
        basis_of_record=basis_of_record,
    )
    Observation.objects.create(
        gbif_id=2, occurrence_id="2", species=second_species,
        date=datetime.date.today(), data_import=di, initial_data_import=di,
        source_dataset=second_dataset, location=Point(4.35978, 50.64728, srid=4326),
        basis_of_record=basis_of_record,
    )
    public_area_andenne = Area.objects.create(
        name="Public polygon - Andenne",
        mpoly=MultiPolygon(
            Polygon(
                ((4.7866, 50.5200), (5.6271, 50.6839), (5.6930, 50.5724),
                 (4.8306, 50.4116), (4.7866, 50.5200)),
                srid=4326,
            ),
            srid=4326,
        ),
    )
    public_area_lillois = Area.objects.create(
        name="Public polygon - Lillois",
        mpoly=MultiPolygon(
            Polygon(
                ((4.3164, 50.6658), (4.4025, 50.6658), (4.4025, 50.6164),
                 (4.3164, 50.6164), (4.3164, 50.6658)),
                srid=4326,
            ),
            srid=4326,
        ),
    )
    User = get_user_model()
    user = User.objects.create_user(
        username="frusciante", password="12345",
        first_name="John", last_name="Frusciante", email="frusciante@gmail.com",
    )
    ObservationUnseen.objects.create(observation=obs, user=user)
    create_or_refresh_all_materialized_views()
    return {
        "basis_of_record": basis_of_record,
        "first_species": first_species,
        "second_species": second_species,
        "di": di,
        "first_dataset": first_dataset,
        "second_dataset": second_dataset,
        "obs": obs,
        "public_area_andenne": public_area_andenne,
        "public_area_lillois": public_area_lillois,
        "user": user,
    }


# ---------------------------------------------------------------------------
# MinMaxPerHexagonTests
# ---------------------------------------------------------------------------

def test_min_max_status_area_combinations(maps_data, client):
    """Regression test for https://github.com/riparias/gbif-alert/issues/283"""
    client.login(username="frusciante", password="12345")
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "status": "viewed",
            "areaIds[]": maps_data["public_area_andenne"].pk,
        },
    )
    assert response.status_code == 200


def test_min_max_per_hexagon(maps_data, client):
    # At zoom level 8, with the initial data: we should have two polygons, both at 1. So min=1 and max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8},
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Add a second one in Lillois, but not next to the other one
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=Species.objects.all()[0],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8, 1, 13])

    # Now, at zoom level 8 we should have a hexagon with count=1 and another one with count=2
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2

    # But at a very large scale, one single hexagon with count=3
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 1},
    )
    assert response.json()["min"] == 3
    assert response.json()["max"] == 3

    # At zoom level 17, there's no hexagons that cover more than 1 observation
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 13},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1


def test_min_max_per_hexagon_with_species_filter(maps_data, client):
    # Add a second one in Lillois, but not next to the other one and another species
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3LKDVC",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "speciesIds[]": maps_data["first_species"].pk},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Now we're looking for the second species. (We have 2 in Lillois and none in Andenne)
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "speciesIds[]": [maps_data["second_species"].pk],
        },
    )

    assert response.json()["min"] == 2
    assert response.json()["max"] == 2

    # Now let's add another one in Andenne for species 2: we should now have 1,2
    Observation.objects.create(
        gbif_id=4,
        occurrence_id="4",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(5.095610, 50.48800, srid=4326),
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "speciesIds[]": maps_data["second_species"].pk},
    )

    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_dataset_filter(maps_data, client):
    # Add a second one in Lillois, but not next to the other one and another species
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3DSRZER",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "datasetsIds[]": maps_data["first_dataset"].pk},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Now we're looking for the second species. (We have 2 in Lillois and none in Andenne)
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "speciesIds[]": [maps_data["second_species"].pk],
        },
    )

    assert response.json()["min"] == 2
    assert response.json()["max"] == 2

    # Now let's add another one in Andenne for species 2: we should now have 1,2
    Observation.objects.create(
        gbif_id=4,
        occurrence_id="4",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(5.095610, 50.48800, srid=4326),
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "speciesIds[]": maps_data["second_species"].pk},
    )

    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_basis_of_record_filter(maps_data, client):
    second_bor = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
    # Add a third observation at the same location as obs2 (Lillois) with a different basis of record
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3BOR",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
        basis_of_record=second_bor,
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # Filter by HUMAN_OBSERVATION: Andenne=1, Lillois=1 -> min=1, max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "basisOfRecordIds[]": maps_data["basis_of_record"].pk},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Filter by MACHINE_OBSERVATION: only Lillois=1 -> min=1, max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "basisOfRecordIds[]": second_bor.pk},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Without filter: Andenne=1, Lillois=2 -> min=1, max=2
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_verified_filter(maps_data, client):
    # Add a third observation at Lillois with verified=True (obs1 and obs2 are unverified by default)
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3VER",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
        basis_of_record=maps_data["basis_of_record"],
        verified=True,
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # Filter for verified only: only obs3 in Lillois -> min=1, max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "verifiedFilter": "verified"},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Filter for unverified only: obs1 in Andenne + obs2 in Lillois -> min=1, max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "verifiedFilter": "unverified"},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Without filter: Andenne=1, Lillois=2 -> min=1, max=2
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_in_hexagon_with_status_filter_invalid_value(maps_data, client):
    """status is not viewed nor notViewed, therefore is ignored and everything is included"""
    client.login(username="frusciante", password="12345")
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 1, "status": "all"},
    )
    assert response.json()["min"] == 2
    assert response.json()["max"] == 2


def test_min_max_in_hexagon_with_status_filter(maps_data, client):
    # Add a second one in Lillois, but not next to the other
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        basis_of_record=maps_data["basis_of_record"],
    )

    client.login(username="frusciante", password="12345")

    # At a zoom level that only shows Lillois or Andenne, it's 1-1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "status": "notViewed",
        },
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1


def test_min_max_in_hexagon_with_status_filter_anonymous(maps_data, client):
    """Similar to test_min_max_in_hexagon_with_status_filter(), but anonymous -> filters get ignored"""
    # Add a second one in Lillois, but not next to the other
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # At a zoom level that only shows Lillois or Andenne, it's 1-1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "status": "notViewed",
        },
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_area_filter(maps_data, client):
    # Add a second one in Lillois, but not next to the other
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois, bakkerij
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # We restrict ourselves to Andenne: only one observation
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "areaIds[]": maps_data["public_area_andenne"].pk,
        },
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Case 2: we limit ourselves to Lillois (one single hexagon, with count=2)
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "areaIds[]": maps_data["public_area_lillois"].pk,
        },
    )
    assert response.json()["min"] == 2
    assert response.json()["max"] == 2

    # Case3: Test with multiple areas: we request both Andenne and Lillois: same results as no filters
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={
            "zoom": 8,
            "areaIds[]": [
                maps_data["public_area_lillois"].pk,
                maps_data["public_area_andenne"].pk,
            ],
        },
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_initial_data_import_filter(maps_data, client):
    second_di = DataImport.objects.create(start=timezone.now())
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["first_species"],
        date=datetime.date.today(),
        data_import=second_di,
        initial_data_import=second_di,
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # Filter by first data import: 2 observations in different hexagons -> min=1, max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "initialDataImportIds[]": maps_data["di"].pk},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Filter by second data import: 1 observation -> min=1, max=1
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "initialDataImportIds[]": second_di.pk},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1

    # Without filter: Andenne has 1, Lillois has 2 -> min=1, max=2
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_start_date_filter(maps_data, client):
    # Add a third observation in Lillois with a recent date
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["first_species"],
        date=datetime.date(2023, 6, 15),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # Without filter: Andenne has 1 obs, Lillois has 2 -> min=1, max=2
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 2

    # With startDate=2022-01-01: obs1 (2020-01-01) excluded, obs2 (today) and obs3 (2023-06-15) remain in Lillois
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "startDate": "2022-01-01"},
    )
    assert response.json()["min"] == 2
    assert response.json()["max"] == 2


def test_min_max_per_hexagon_with_end_date_filter(maps_data, client):
    # Add a third observation in Lillois with a recent date
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["first_species"],
        date=datetime.date(2023, 6, 15),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )

    create_or_refresh_materialized_views(zoom_levels=[8])

    # With endDate=2022-02-02: only obs1 (2020-01-01) in Andenne remains
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
        data={"zoom": 8, "endDate": "2022-02-02"},
    )
    assert response.json()["min"] == 1
    assert response.json()["max"] == 1


def test_min_max_per_hexagon_no_zoom(maps_data, client):
    """When zoom is not provided, the view returns a 400 error"""
    response = client.get(
        reverse("dashboard:internal-api:maps:mvt-min-max-per-hexagon"),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# MVTServerSingleObsTests  (server_url_name = "dashboard:internal-api:maps:mvt-tiles")
# ---------------------------------------------------------------------------

_SINGLE_OBS_URL = "dashboard:internal-api:maps:mvt-tiles"


def _build_single_obs_tile_url(zoom: int) -> str:
    return reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": zoom, "x": 0, "y": 0},
    )


def test_single_obs_status_and_content_type(maps_data, client):
    """The server responds with the correct status code and content-type"""
    response = client.get(_build_single_obs_tile_url(zoom=1))
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/vnd.mapbox-vector-tile"


def test_single_obs_zoom_levels(maps_data, client):
    """Zoom levels 0-14 are supported"""
    for zoom_level in range(0, 14):
        response = client.get(_build_single_obs_tile_url(zoom=zoom_level))
        assert response.status_code == 200
        mapbox_vector_tile.decode(response.content)


def test_tiles_features_type(maps_data, client):
    """The server return points"""
    response = client.get(
        reverse(
            _SINGLE_OBS_URL,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    for feature in decoded_tile["default"]["features"]:
        assert feature["geometry"]["type"] == "Point"


def test_tiles_no_filter(maps_data, client):
    # Case 1: A large view over Wallonia
    response = client.get(
        reverse(
            _SINGLE_OBS_URL,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    # 2 points are present
    assert len(decoded_tile["default"]["features"]) == 2
    for feature in decoded_tile["default"]["features"]:
        assert feature["properties"]["gbif_id"] in ["1", "2"]

    # Case 2: Zoom to Andenne
    response = client.get(
        reverse(
            _SINGLE_OBS_URL,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
    )

    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"


def test_tiles_area_filter(maps_data, client):
    # Case 1: A large view over Wallonia
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    url_with_params = f"{base_url}?areaIds[]={maps_data['public_area_andenne'].pk}"

    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    # only one point is present because of the area filtering
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"

    # Case 2: Zoom to Andenne, the point there shouldn't be impacted by the filtering
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?areaIds[]={maps_data['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)

    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"


def test_tiles_dataset_filter(maps_data, client):
    # Case 1: A large view over Wallonia
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    url_with_params = f"{base_url}?datasetsIds[]={maps_data['second_dataset'].pk}"

    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    # only one point is present because of the dataset filtering
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "2"

    # Case 2: Zoom to Andenne, there should be no observation because of the filtering
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?datasetsIds[]={maps_data['second_dataset'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # Case 3: Zoom to Lillois, the obs should be seen again
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 17, "x": 67123, "y": 44083},
    )
    url_with_params = f"{base_url}?datasetsIds[]={maps_data['second_dataset'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "2"


def test_tiles_basis_of_record_filter(maps_data, client):
    second_bor = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
    # Add a third observation at the same location as obs2 (Lillois) with a different basis of record
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3BOR",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
        basis_of_record=second_bor,
    )

    # Case 1: A large view over Wallonia, filter by MACHINE_OBSERVATION
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    # Only the new observation should be present
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "3"

    # Case 2: Zoom to Andenne, filter by MACHINE_OBSERVATION: no observation
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # Case 3: Zoom to Lillois, filter by MACHINE_OBSERVATION: obs3 visible
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 17, "x": 67123, "y": 44083},
    )
    url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "3"


def test_tiles_verified_filter(maps_data, client):
    # Add a third observation at Lillois with verified=True (obs1 and obs2 are unverified by default)
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3VER",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
        basis_of_record=maps_data["basis_of_record"],
        verified=True,
    )

    # Case 1: Large view over Wallonia, filter by verified: only obs3
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?verifiedFilter=verified"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "3"

    # Case 2: Filter by unverified: obs1 and obs2 only (2 features)
    url_with_params = f"{base_url}?verifiedFilter=unverified"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 2
    gbif_ids = {f["properties"]["gbif_id"] for f in decoded_tile["default"]["features"]}
    assert gbif_ids == {"1", "2"}

    # Case 3: Zoom to Andenne, filter by verified: no obs (obs1 in Andenne is unverified)
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?verifiedFilter=verified"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_tiles_start_date_filter(maps_data, client):
    """Use the startDate parameter to filter out observations that are too old"""
    # Case 1: A large view over Wallonia
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    url_with_params = f"{base_url}?startDate=2022-01-01"

    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    # only one point is present because of the date filtering
    assert len(decoded_tile["default"]["features"]) == 1
    # It's the one in Lillois
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "2"

    # Case 2: Zoom to Andenne, there should be no observation because of the filtering
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?startDate=2022-01-01"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # Case 3: Zoom to Lillois, the obs should be seen again
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 17, "x": 67123, "y": 44083},
    )
    url_with_params = f"{base_url}?startDate=2022-01-01"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "2"


def test_tiles_end_date_filter(maps_data, client):
    """Use the endDate parameter to filter out observations that are too recent"""
    # Case 1: A large view over Wallonia
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    url_with_params = f"{base_url}?endDate=2022-02-02"

    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    # only one point is present because of the date filtering
    assert len(decoded_tile["default"]["features"]) == 1
    # It's the one in Andenne
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"

    # Case 2: Zoom to Andenne, there should be one observation
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?endDate=2022-02-02"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"

    # Case 3: Zoom to Lillois, there should be no obs
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 17, "x": 67123, "y": 44083},
    )
    url_with_params = f"{base_url}?endDate=2022-02-02"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_tiles_combined_filters(maps_data, client):
    # Test a combination of filters per status (viewed/notViewed) and species
    client.login(username="frusciante", password="12345")

    # Case 1: Large-scale view: a single hex over Wallonia
    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    # First, all seen observations for the user => only the one in Lillois
    url_with_params = f"{base_url}?status=viewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "2"

    # All unseen observations => only the one in Andenne
    url_with_params = f"{base_url}?status=notViewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"

    # Same, but we add some species filtering that doesn't filter anything out
    url_with_params = (
        f"{base_url}?status=notViewed&speciesIds[]={maps_data['first_species'].pk}"
    )
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"

    # Finally, we remove the observation by applying another species filter
    url_with_params = (
        f"{base_url}?status=notViewed&speciesIds[]={maps_data['second_species'].pk}"
    )
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_tiles_status_filter_frontend_vocabulary(maps_data, client):
    """Regression test: the frontend map sends the external status vocabulary
    ("viewed"/"notViewed"), not the internal one ("seen"/"unseen"). The tile
    endpoints must translate it; otherwise the status filter is silently
    dropped and every observation shows on the map regardless of its status.

    See the map/table consistency note at the top of dashboard/views/maps.py.
    """
    client.login(username="frusciante", password="12345")
    base_url = reverse(_SINGLE_OBS_URL, kwargs={"zoom": 2, "x": 2, "y": 1})

    # "viewed" => only the seen observation (Lillois, gbif_id=2)
    response = client.get(f"{base_url}?status=viewed")
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "2"

    # "notViewed" => only the unseen observation (Andenne, gbif_id=1)
    response = client.get(f"{base_url}?status=notViewed")
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "1"


def test_tiles_initial_data_import_filter(maps_data, client):
    second_di = DataImport.objects.create(start=timezone.now())
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["first_species"],
        date=datetime.date.today(),
        data_import=second_di,
        initial_data_import=second_di,
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )

    base_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    # Filter by first data import: only the 2 original observations
    url_with_params = f"{base_url}?initialDataImportIds[]={maps_data['di'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 2

    # Filter by second data import: only the new observation
    url_with_params = f"{base_url}?initialDataImportIds[]={second_di.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["gbif_id"] == "3"


def test_tiles_vernacular_name_in_active_language(maps_data, client):
    """Tile properties include the vernacular name for the active language."""
    tile_url = reverse(
        _SINGLE_OBS_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    maps_data["first_species"].vernacular_name_en = "Marbled crayfish"
    maps_data["first_species"].vernacular_name_nl = "Marmerkreeft"
    maps_data["first_species"].vernacular_name_fr = "Ecrevisse marbre"
    maps_data["first_species"].save()

    # The language selector sets a django_language cookie; simulate that here.
    # (The browser's Accept-Language header is always en-US regardless of the UI language.)
    features_by_gbif_id = None
    for lang_code, expected_name in [
        ("en", "Marbled crayfish"),
        ("nl", "Marmerkreeft"),
        ("fr", "Ecrevisse marbre"),
    ]:
        client.cookies["django_language"] = lang_code
        response = client.get(tile_url)
        decoded_tile = mapbox_vector_tile.decode(response.content)
        features_by_gbif_id = {
            f["properties"]["gbif_id"]: f
            for f in decoded_tile["default"]["features"]
        }
        assert (
            features_by_gbif_id["1"]["properties"]["vernacular_name"] == expected_name
        ), f"Wrong vernacular name for language '{lang_code}'"

    # A species with no vernacular name should have no vernacular_name property in the tile
    assert "vernacular_name" not in features_by_gbif_id["2"]["properties"]


# ---------------------------------------------------------------------------
# MVTServerAggregatedObsTests
# (server_url_name = "dashboard:internal-api:maps:mvt-tiles-hexagon-grid-aggregated")
# ---------------------------------------------------------------------------

_AGGREGATED_URL = "dashboard:internal-api:maps:mvt-tiles-hexagon-grid-aggregated"


def _build_aggregated_tile_url(zoom: int) -> str:
    return reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": zoom, "x": 0, "y": 0},
    )


def test_aggregated_status_and_content_type(maps_data, client):
    """The server responds with the correct status code and content-type"""
    response = client.get(_build_aggregated_tile_url(zoom=1))
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/vnd.mapbox-vector-tile"


def test_aggregated_zoom_levels(maps_data, client):
    """Zoom levels 0-14 are supported"""
    for zoom_level in range(0, 14):
        response = client.get(_build_aggregated_tile_url(zoom=zoom_level))
        assert response.status_code == 200
        mapbox_vector_tile.decode(response.content)


def test_aggregated_tiles_features_type(maps_data, client):
    """The server return 6-sided polygons"""
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    for feature in decoded_tile["default"]["features"]:
        assert feature["geometry"]["type"] == "Polygon"
        assert len(feature["geometry"]["coordinates"][0]) == 7  # 7 coordinates pair = 6 sides


def test_aggregated_tiles_null_filters_ignored(maps_data, client):
    """Regression test: filters at null in the URL don't create problems, the filter is just ignored.

    Derived from test_basic_data_in_hexagons()
    """
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?startDate=null&endDate=null"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)

    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 2  # It has a "count" property with the value 2


def test_aggregated_tiles_area_filter(maps_data, client):
    # We explore tiles at different zoom levels. In all cases the observation in Lillois should be filtered out by
    # the areaId filtering.

    # Case 1: large view over Wallonia
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},  # Large views over Wallonia
    )
    url_with_params = f"{base_url}?areaIds[]={maps_data['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)

    # We have one single hexagon (because of the zoom level), its counter is 1 (because Lillois observation was filtered out)
    assert len(decoded_tile["default"]["features"]) == 1
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 1

    # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
    # hexagon (because of the area filtering)
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 8, "x": 131, "y": 86},
    )
    url_with_params = f"{base_url}?areaIds[]={maps_data['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?areaIds[]={maps_data['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 4: A zoomed time on Lillois, should be empty because of the filtering
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?areaIds[]={maps_data['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_status_filter_anonymous(maps_data, client):
    """Similar to test_tiles_status_filter_case1() but anonymous => filter is ignored"""
    # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?status=viewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 2


def test_aggregated_tiles_status_filter_invalid_filter_value(maps_data, client):
    """Similar to test_tiles_status_filter_case1() but with a filter that's not viewed | notViewed => filter is ignored
    and everything is included"""
    # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
    client.login(username="frusciante", password="12345")
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?status=all"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 2


def test_aggregated_tiles_status_filter_case1(maps_data, client):
    client.login(username="frusciante", password="12345")
    # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?status=viewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 1  # Only one observation this time, due to the filter


def test_aggregated_tiles_status_filter_case2(maps_data, client):
    client.login(username="frusciante", password="12345")
    # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?status=notViewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)

    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 1  # Only one observation this time (the one in Andenne), due to the filter

    # Case 2: zoom a bit to make sure it's the one in Andenne

    # Case 2.1: it still appears when zoomed on Andenne
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?status=notViewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 2.2: there's nothing when zoomed on Lillois
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?status=notViewed"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_species_filter(maps_data, client):
    # We explore tiles at different zoom levels. In all cases the observation in Lillois should be filtered out by
    # the speciesId filtering.
    # Multiple cases where only the observation in Andenne is visible

    # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 1  # Only one observation this time, due to the filter

    # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
    # polygon this time
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 8, "x": 131, "y": 86},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 4: A zoomed time on Lillois, should be empty because of the filtering
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_multiple_dataset_filters(maps_data, client):
    """Explicitly requesting all datasets give the same results as no filtering"""
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?&datasetsIds[]={maps_data['first_dataset'].pk}&datasetsIds[]={maps_data['second_dataset'].pk}"
    response = client.get(url_with_params)
    decoded_tile_explicit_filters = mapbox_vector_tile.decode(response.content)

    response = client.get(base_url)
    decoded_tile_no_filters = mapbox_vector_tile.decode(response.content)

    assert decoded_tile_no_filters == decoded_tile_explicit_filters


def test_aggregated_tiles_dataset_filter(maps_data, client):
    # Inspired by test_tiles_species_filter

    # Multiple cases where only the observation in Andenne is visible
    # (because we only ask for the first dataset)

    # Case 1: Large-scale view: a single hex over Wallonia, but count = 1
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?&datasetsIds[]={maps_data['first_dataset'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 1  # Only one observation this time, due to the filter

    # Case 2: A tile that covers an important part of Wallonia, including Andenne and Braine. Should have a single
    # polygon this time
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 8, "x": 131, "y": 86},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 4: A zoomed time on Lillois, should be empty because of the filtering
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_basis_of_record_filter(maps_data, client):
    second_bor = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
    # Add a third observation at the same location as obs2 (Lillois) with a different basis of record
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3BOR",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
        basis_of_record=second_bor,
    )

    # Case 1: Large-scale view: a single hex over Wallonia
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    # Filter by HUMAN_OBSERVATION: count should be 2 (obs1 + obs2)
    url_with_params = f"{base_url}?basisOfRecordIds[]={maps_data['basis_of_record'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 2

    # Filter by MACHINE_OBSERVATION: count should be 1 (only obs3 in Lillois)
    url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 2: Zoom on Andenne, filter by MACHINE_OBSERVATION: should be empty
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # Case 3: Zoom on Lillois, filter by MACHINE_OBSERVATION: count=1
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?basisOfRecordIds[]={second_bor.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1


def test_aggregated_tiles_verified_filter(maps_data, client):
    # Add a third observation at Lillois with verified=True (obs1 and obs2 are unverified by default)
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3VER",
        species=maps_data["second_species"],
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["second_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois (same as obs2)
        basis_of_record=maps_data["basis_of_record"],
        verified=True,
    )

    # Case 1: Large-scale view over Wallonia (single hex)
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    # Filter by verified: count should be 1 (only obs3)
    url_with_params = f"{base_url}?verifiedFilter=verified"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Filter by unverified: count should be 2 (obs1 + obs2)
    url_with_params = f"{base_url}?verifiedFilter=unverified"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 2

    # Case 2: Zoom on Andenne, filter by verified: should be empty (obs1 is unverified)
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?verifiedFilter=verified"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_species_multiple_species_filters(maps_data, client):
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
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )
    Observation.objects.create(
        gbif_id=1001,
        occurrence_id="1001",
        species=species_tetraodon,
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )
    Observation.objects.create(
        gbif_id=1002,
        occurrence_id="1002",
        species=species_tetraodon,
        date=datetime.date.today(),
        data_import=maps_data["di"],
        initial_data_import=maps_data["di"],
        source_dataset=maps_data["first_dataset"],
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )

    # Case 1: Large-scale view: a single hex over Wallonia
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}&speciesIds[]={species_tetraodon.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 4  # 3 in Lillois (tetraodon, 1 in Andenne)

    # Case 2: A tile that covers an important part of Wallonia, including Andenne and Lillois. Should have two polygons
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 8, "x": 131, "y": 86},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}&speciesIds[]={species_tetraodon.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 2

    # We should have one observation in Andenne (for first species) and 3 in Lillois (for tetraodon)
    for entry in decoded_tile["default"]["features"]:
        assert entry["properties"]["count"] in [1, 3]

    # Case 3: A zoomed tile with just Andenne and the close neighborhood, the hex should still be there
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}&speciesIds[]={species_tetraodon.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Case 4: A zoomed time on Lillois, we expect the three tetraodon observations
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?speciesIds[]={maps_data['first_species'].pk}&speciesIds[]={species_tetraodon.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 3


def test_aggregated_tiles_basic_data_in_hexagons(maps_data, client):
    # Very large view (big part of Europe, Africa and Russia: we expect a single hexagon over Belgium
    #
    # Those tests can be more easily debugged with a "TileDebug" layer in OpenLayers:
    # https://openlayers.org/en/latest/examples/canvas-tiles.html
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 2, "x": 2, "y": 1},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)

    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    the_feature = decoded_tile["default"]["features"][0]
    assert the_feature["properties"]["count"] == 2  # It has a "count" property with the value 2
    assert the_feature["geometry"]["type"] == "Polygon"  # the feature is a polygon
    assert len(the_feature["geometry"]["coordinates"][0]) == 7  # 7 coordinates pair = 6 sides

    # Another very large tile, over Greenland. Should be empty
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 2, "x": 1, "y": 0},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # A tile that covers an important part of Wallonia, including Andenne and Braine. Should have two polygons
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 8, "x": 131, "y": 86},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 2  # it has two features

    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1
    assert decoded_tile["default"]["features"][1]["properties"]["count"] == 1

    # The tile east of it should be empty
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 8, "x": 132, "y": 86},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # A tile with just Andenne and the close neighborhood
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 10, "x": 526, "y": 345},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # The one on the west is empty
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 10, "x": 525, "y": 345},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}

    # Let's get a very small tile containing the Lillois observations
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 14, "x": 8390, "y": 5510},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1  # it has a single feature
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # The next tile is empty
    response = client.get(
        reverse(
            _AGGREGATED_URL,
            kwargs={"zoom": 14, "x": 8391, "y": 5510},
        )
    )
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_initial_data_import_filter(maps_data, client):
    second_di = DataImport.objects.create(start=timezone.now())
    Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=maps_data["first_species"],
        date=datetime.date.today(),
        data_import=second_di,
        initial_data_import=second_di,
        source_dataset=maps_data["first_dataset"],
        location=Point(4.36229, 50.64628, srid=4326),  # Lillois
        basis_of_record=maps_data["basis_of_record"],
    )

    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    # Filter by first data import: one hexagon with count=2
    url_with_params = f"{base_url}?initialDataImportIds[]={maps_data['di'].pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 2

    # Filter by second data import: one hexagon with count=1
    url_with_params = f"{base_url}?initialDataImportIds[]={second_di.pk}"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1


def test_aggregated_tiles_start_date_filter(maps_data, client):
    """Use the startDate parameter to filter out old observations"""
    # At zoom 2: both observations are in one hexagon.
    # obs1 is 2020-01-01 (Andenne), obs2 is today (Lillois).
    # startDate=2022-01-01 should exclude obs1, leaving count=1.
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    url_with_params = f"{base_url}?startDate=2022-01-01"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Zoomed on Andenne: should be empty because the old observation is filtered out
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 10, "x": 526, "y": 345},
    )
    url_with_params = f"{base_url}?startDate=2022-01-01"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}


def test_aggregated_tiles_end_date_filter(maps_data, client):
    """Use the endDate parameter to filter out recent observations"""
    # endDate=2022-02-02 should exclude obs2 (today), leaving only obs1 (2020-01-01).
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 2, "x": 2, "y": 1},
    )

    url_with_params = f"{base_url}?endDate=2022-02-02"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert len(decoded_tile["default"]["features"]) == 1
    assert decoded_tile["default"]["features"][0]["properties"]["count"] == 1

    # Zoomed on Lillois: should be empty because the recent observation is filtered out
    base_url = reverse(
        _AGGREGATED_URL,
        kwargs={"zoom": 14, "x": 8390, "y": 5510},
    )
    url_with_params = f"{base_url}?endDate=2022-02-02"
    response = client.get(url_with_params)
    decoded_tile = mapbox_vector_tile.decode(response.content)
    assert decoded_tile == {}
