import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse
from django.utils import timezone

from dashboard.models import (
    Area, BasisOfRecord, DataImport, Dataset, Observation, ObservationUnseen, Species,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()
OCTOBER_8_2021 = datetime.datetime.strptime("2021-10-08", "%Y-%m-%d").date()

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_api_data():
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")

    first_species = Species.objects.create(
        name="Procambarus fallax", gbif_taxon_key=8879526
    )
    second_species = Species.objects.create(
        name="Orconectes virilis", gbif_taxon_key=2227064
    )

    mocked = datetime.datetime(2022, 2, 11, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
    with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
        di = DataImport.objects.create(start=timezone.now())

    first_dataset = Dataset.objects.create(
        name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
    )
    second_dataset = Dataset.objects.create(
        name="Test dataset #2",
        gbif_dataset_key="aaa7b334-ce0d-4e88-aaae-2e0c138d049f",
    )

    obs1 = Observation.objects.create(
        gbif_id=1,
        occurrence_id="1",
        species=first_species,
        date=SEPTEMBER_13_2021,
        data_import=di,
        initial_data_import=di,
        source_dataset=first_dataset,
        location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        basis_of_record=basis_of_record,
    )
    obs2 = Observation.objects.create(
        gbif_id=2,
        occurrence_id="2",
        species=second_species,
        date=SEPTEMBER_13_2021,
        data_import=di,
        initial_data_import=di,
        source_dataset=second_dataset,
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        basis_of_record=basis_of_record,
    )
    obs3 = Observation.objects.create(
        gbif_id=3,
        occurrence_id="3",
        species=second_species,
        date=OCTOBER_8_2021,
        data_import=di,
        initial_data_import=di,
        source_dataset=first_dataset,
        location=Point(4.35978, 50.64728, srid=4326),  # Lillois
        basis_of_record=basis_of_record,
    )

    public_area_andenne = Area.objects.create(
        name="Public polygon - Andenne",
        # Covers Namur-Liege area (includes Andenne but not Lillois)
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

    public_area_lillois = Area.objects.create(
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
    area_owner = User.objects.create_user(
        username="frusciante",
        password="12345",
        first_name="John",
        last_name="Frusciante",
        email="frusciante@gmail.com",
    )

    another_user = User.objects.create_user(
        username="frusciante1",
        password="12345",
        first_name="John",
        last_name="Frusciante",
        email="frusciante1@gmail.com",
    )

    user_area = Area.objects.create(
        name="User polygon",
        owner=area_owner,
        mpoly=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
    )

    # Initial situation: only obs2 has been seen by "another user"
    ObservationUnseen.objects.create(observation=obs1, user=area_owner)
    ObservationUnseen.objects.create(observation=obs1, user=another_user)
    ObservationUnseen.objects.create(observation=obs2, user=area_owner)
    ObservationUnseen.objects.create(observation=obs3, user=area_owner)
    ObservationUnseen.objects.create(observation=obs3, user=another_user)

    return {
        "basis_of_record": basis_of_record,
        "first_species": first_species,
        "second_species": second_species,
        "di": di,
        "first_dataset": first_dataset,
        "second_dataset": second_dataset,
        "obs1": obs1,
        "obs2": obs2,
        "obs3": obs3,
        "public_area_andenne": public_area_andenne,
        "public_area_lillois": public_area_lillois,
        "area_owner": area_owner,
        "another_user": another_user,
        "user_area": user_area,
    }


def _wfs_capabilities(client) -> str:
    base_url = reverse("dashboard:public-api:wfs-observations")
    resp = client.get(f"{base_url}?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0")
    assert resp.status_code == 200
    return resp.content.decode()


def test_wfs_capabilities_uses_site_name_in_title(client, settings):
    """The WFS GetCapabilities title is derived from SITE_NAME (not 'Unnamed')."""
    settings.GBIF_ALERT = {**settings.GBIF_ALERT, "SITE_NAME": "Test Portal"}
    body = _wfs_capabilities(client)
    assert "Unnamed" not in body
    assert "Test Portal - observations" in body


def test_wfs_capabilities_title_falls_back_without_site_name(client, settings):
    """With no SITE_NAME configured, the title falls back to 'GBIF Alert'."""
    settings.GBIF_ALERT = {**settings.GBIF_ALERT, "SITE_NAME": ""}
    body = _wfs_capabilities(client)
    assert "Unnamed" not in body
    assert "GBIF Alert - observations" in body


def test_observations_json_view_data(public_api_data, client):
    """If the user is authenticated, there is data about which observations were already seen by that user"""
    client.login(username="frusciante1", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id")
    json_data = response.json()
    assert json_data["results"][0]["seenByCurrentUser"] == False
    assert json_data["results"][1]["seenByCurrentUser"] == True


def test_observations_json_no_view_for_anonymous(public_api_data, client):
    """If the user is anonymous, there is NO data about which observations were already seen"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1")
    json_data = response.json()
    with pytest.raises(KeyError):
        json_data["results"][0]["seenByCurrentUser"]


def test_observations_json_no_location(public_api_data, client):
    """Regression test: no error 500 in observations_json if we have locations without a location"""
    d = public_api_data
    Observation.objects.create(
        gbif_id=4,
        occurrence_id="4",
        species=d["second_species"],
        date=datetime.date.today(),
        data_import=d["di"],
        initial_data_import=d["di"],
        source_dataset=d["first_dataset"],
        location=None,
        basis_of_record=d["basis_of_record"],
    )
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 4


def test_observations_json_basic_no_filters(public_api_data, client):
    """Basic tests for the endpoint, no filters used"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1")
    assert response.status_code == 200
    json_data = response.json()
    # All 3 observations should be on this first page, in undefined order
    assert json_data["totalResultsCount"] == 3
    assert json_data["totalResultsCount"] == len(json_data["results"])
    assert json_data["pageNumber"] == 1
    assert json_data["firstPage"] == 1
    assert json_data["lastPage"] == 1
    found = False
    for r in json_data["results"]:
        if r["scientificName"] == "Procambarus fallax":
            found = True
    assert found


def test_observation_json_short_results(public_api_data, client):
    """Test the short results mode"""
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&mode=short")
    assert response.status_code == 200
    json_data = response.json()

    results = json_data["results"]

    # Check the correct records are present
    ids_in_results = [result["id"] for result in results]
    assert ids_in_results == [d["obs1"].pk, d["obs2"].pk, d["obs3"].pk]

    # check the fields that are present in the short mode
    for result in results:
        assert "id" in result
        assert "lat" in result
        assert "lon" in result
        assert "scientificName" in result
        assert "speciesId" in result
        assert "date" in result
        # Check fields that should not be present in the short mode
        assert "stableId" not in result


def test_observations_json_default_mode_normal(public_api_data, client):
    """Explicitly asking the normal mode brings the same result as not specifying a mode"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response_normal = client.get(f"{base_url}?limit=10&page_number=1")
    response_no_mode = client.get(f"{base_url}?limit=10&page_number=1&mode=normal")
    assert response_normal.status_code == 200
    assert response_no_mode.status_code == 200
    assert response_normal.json() == response_no_mode.json()


def test_observations_json_ordering_pk(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=-pk")
    assert response.status_code == 200
    json_data = response.json()
    # Check that it's sorted by reverse primary key
    received_pks = [e["id"] for e in json_data["results"]]
    assert received_pks[::-1] == sorted(received_pks)


def test_observations_json_ordering_gbif_id(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id")
    assert response.status_code == 200
    json_data = response.json()
    # Check that it's sorted by GBIF ID
    assert json_data["results"][0]["gbifId"] == "1"
    assert json_data["results"][1]["gbifId"] == "2"
    assert json_data["results"][2]["gbifId"] == "3"


def test_observations_json_ordering_species_name_asc(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=species__name")
    assert response.status_code == 200
    json_data = response.json()
    # Check that it's sorted by species name (alphabetical order)
    obs_species_names = [result["scientificName"] for result in json_data["results"]]
    assert obs_species_names == sorted(obs_species_names)


def test_observations_json_ordering_species_name_desc(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=-species__name")
    assert response.status_code == 200
    json_data = response.json()
    # Check that it's sorted by species name (alphabetical order)
    obs_species_names = [result["scientificName"] for result in json_data["results"]]
    assert obs_species_names[::-1] == sorted(obs_species_names)


def test_observations_json_pagination_base(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    response = client.get(f"{base_url}?limit=2&page_number=1")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 3
    assert len(json_data["results"]) == 2
    assert json_data["firstPage"] == 1
    assert json_data["lastPage"] == 2
    assert json_data["pageNumber"] == 1

    response = client.get(f"{base_url}?limit=2&page_number=2")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 3
    assert len(json_data["results"]) == 1
    assert json_data["firstPage"] == 1
    assert json_data["lastPage"] == 2
    assert json_data["pageNumber"] == 2


def test_observations_json_pagination_greater_than_max(public_api_data, client):
    """If the requested page number is greater than the number of pages, it returns the last page"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=2&page_number=3")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 3
    assert len(json_data["results"]) == 1
    assert json_data["firstPage"] == 1
    assert json_data["lastPage"] == 2
    assert json_data["pageNumber"] == 2


def test_observations_json_pagination_negative(public_api_data, client):
    """If the requested page number is negative, it returns the last page"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=2&page_number=-5")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 3
    assert len(json_data["results"]) == 1
    assert json_data["firstPage"] == 1
    assert json_data["lastPage"] == 2
    assert json_data["pageNumber"] == 2


def test_observations_json_min_date_filter(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(
        f"{base_url}?limit=10&page_number=1&startDate={OCTOBER_8_2021.strftime('%Y-%m-%d')}"
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1
    assert json_data["results"][0]["gbifId"] == "3"


def test_observations_json_max_date_filter(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(
        f"{base_url}?limit=10&page_number=1&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}"
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["totalResultsCount"] == 2
    assert json_data["results"][0]["gbifId"] in ["1", "2"]
    assert json_data["results"][1]["gbifId"] in ["1", "2"]


def test_observations_json_species_filter(public_api_data, client):
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 2
    assert json_data["results"][0]["gbifId"] in ["2", "3"]
    assert json_data["results"][1]["gbifId"] in ["2", "3"]


def test_observations_json_dataset_filter(public_api_data, client):
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&datasetsIds[]={d['first_dataset'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 2
    assert json_data["results"][0]["gbifId"] in ["1", "3"]
    assert json_data["results"][1]["gbifId"] in ["1", "3"]


def test_observations_json_basis_of_record_filter(public_api_data, client):
    """We can filter observations by basis of record"""
    d = public_api_data
    # Create a second basis of record and assign it to obs3
    machine_obs = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
    d["obs3"].basis_of_record = machine_obs
    d["obs3"].save()

    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    # Filter by HUMAN_OBSERVATION: should return obs1 and obs2
    url_with_params = f"{base_url}?limit=10&page_number=1&basisOfRecordIds[]={d['basis_of_record'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 2

    # Filter by MACHINE_OBSERVATION: should return obs3 only
    url_with_params = f"{base_url}?limit=10&page_number=1&basisOfRecordIds[]={machine_obs.pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1
    assert json_data["results"][0]["gbifId"] == "3"


def test_observations_json_area_filter(public_api_data, client):
    """We filter by a single area"""
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&areaIds[]={d['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1
    assert json_data["results"][0]["gbifId"] == "1"  # Only one observation in Andenne because of the selected area


def test_observations_json_status_filter_invalid_value(public_api_data, client):
    """Filtered observations: status is ignored not seen nor unseen"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    response = client.get(f"{base_url}?limit=10&page_number=1")
    unfiltered_results = response.json()

    response = client.get(f"{base_url}?limit=10&page_number=1&status=all")
    results = response.json()
    assert results == unfiltered_results

    response = client.get(f"{base_url}?limit=10&page_number=1&status=dfsfsdfsfsdfs")
    results = response.json()
    assert results == unfiltered_results


def test_observations_json_status_filter_anonymous(public_api_data, client):
    """Filtered observations: status is ignored if the user is anonymous"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    response = client.get(f"{base_url}?limit=10&page_number=1")
    unfiltered_results = response.json()

    response = client.get(f"{base_url}?limit=10&page_number=1&status=seen")
    filtered_seen_results = response.json()
    assert filtered_seen_results == unfiltered_results

    response = client.get(f"{base_url}?limit=10&page_number=1&status=unseen")
    filtered_unseen_results = response.json()
    assert filtered_unseen_results == unfiltered_results


def test_observations_json_status_filter_logged(public_api_data, client):
    """Observations can be filtered by status for authenticated users"""
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id")
    unfiltered_results = response.json()
    unfiltered_results_ids = [r["id"] for r in unfiltered_results["results"]]

    # Case 1: this user hasn't seen any observation
    client.login(username="frusciante", password="12345")

    # Case 1.1: asking seen observations => 0 results
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id&status=seen")
    filtered_seen_results = response.json()
    assert filtered_seen_results["totalResultsCount"] == 0

    # case 1.2: asking unseen observations => same results than no filtering
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id&status=unseen")
    filtered_unseen_results = response.json()
    filtered_unseen_results_ids = [r["id"] for r in filtered_unseen_results["results"]]

    # We have to compare IDs rather than full record, because if the user is authenticated there's also the "seenByCurrentUser" field
    assert filtered_unseen_results_ids == unfiltered_results_ids

    # Case 2: this user has one seen observation
    # Case 2.1: asking seen observations
    client.login(username="frusciante1", password="12345")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id&status=seen")
    filtered_seen_results = response.json()
    assert filtered_seen_results["totalResultsCount"] == 1
    assert (
        filtered_seen_results["results"][0]["stableId"]
        == "4b8dc5900ede9a5850cba11be6aba60315b0f04e"
    )

    # Case 2.2: asking unseen observations
    client.login(username="frusciante1", password="12345")
    response = client.get(f"{base_url}?limit=10&page_number=1&order=gbif_id&status=unseen")
    filtered_unseen_results = response.json()
    filtered_unseen_results_gbif_ids = [r["gbifId"] for r in filtered_unseen_results["results"]]
    assert filtered_unseen_results_gbif_ids == ["1", "3"]


def test_observations_json_no_repeated_queries(public_api_data, client, django_assert_num_queries):
    """Getting occurrences doesn't generate a deluge of queries to the dataset and species tables"""
    with django_assert_num_queries(2):
        client.get(reverse("dashboard:public-api:filtered-observations-data-page"))


def test_observations_json_multiple_areas_filter(public_api_data, client):
    """The areaIds parameter can take multiple values (OR)"""
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&areaIds[]={d['public_area_andenne'].pk}&areaIds[]={d['public_area_lillois'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 3  # All 3 observations should be there because the two areas cover them all


def test_observations_json_multiple_datasets_filter_case1(public_api_data, client):
    """observations_json accept to filter per multiple datasets

    Case 1: Explicitly requests all datasets. Results should be the same as no filter
    """
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    json_data_all_species = client.get(
        f"{base_url}?limit=10&page_number=1&datasetsIds[]={d['first_dataset'].pk}&datasetsIds[]={d['second_dataset'].pk}&order=id"
    ).json()
    json_data_no_species_filters = client.get(
        f"{base_url}?limit=10&page_number=1&order=id"
    ).json()
    assert json_data_all_species == json_data_no_species_filters


def test_observations_json_multiple_species_filter_case1(public_api_data, client):
    """observations_json accept to filter per multiple species

    Case 1: Explicitly requests all species. Results should be the same as no filter
    """
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    json_data_all_species = client.get(
        f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&speciesIds[]={d['first_species'].pk}&order=id"
    ).json()
    json_data_no_species_filters = client.get(
        f"{base_url}?limit=10&page_number=1&order=id"
    ).json()
    assert json_data_all_species == json_data_no_species_filters


def test_observations_json_multiple_species_filter_case2(public_api_data, client):
    """observations_json accept to filter per multiple species

    Case 2: request observations for species 1 and 3
    """
    d = public_api_data
    # We need one more species and one related observation to perform this test
    species_tetraodon = Species.objects.create(
        name="Tetraodon fluviatilis", gbif_taxon_key=5213564
    )
    Observation.objects.create(
        gbif_id=1000,
        species=species_tetraodon,
        date=datetime.date.today(),
        data_import=d["di"],
        initial_data_import=d["di"],
        source_dataset=d["first_dataset"],
        basis_of_record=d["basis_of_record"],
    )

    base_url = reverse("dashboard:public-api:filtered-observations-data-page")

    json_data = client.get(
        f"{base_url}?limit=10&page_number=1&speciesIds[]={d['first_species'].pk}&speciesIds[]={species_tetraodon.pk}"
    ).json()

    assert json_data["totalResultsCount"] == 2
    for result in json_data["results"]:
        assert result["scientificName"] in [d["first_species"].name, species_tetraodon.name]


def test_observations_json_multiple_dataset_filter_case2(public_api_data, client):
    """observations_json accept to filter per multiple datasets
    Case 2: request observations for datasets 1 and 3
    """
    d = public_api_data
    # We need one more dataset and one related observation to perform this test
    third_dataset = Dataset.objects.create(
        name="Third dataset", gbif_dataset_key="xxxx"
    )
    Observation.objects.create(
        gbif_id=1000,
        species=d["first_species"],
        date=datetime.date.today(),
        data_import=d["di"],
        initial_data_import=d["di"],
        source_dataset=third_dataset,
        basis_of_record=d["basis_of_record"],
    )
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    json_data = client.get(
        f"{base_url}?limit=10&page_number=1&datasetsIds[]={d['first_dataset'].pk}&datasetsIds[]={third_dataset.pk}"
    ).json()
    assert json_data["totalResultsCount"] == 3
    for result in json_data["results"]:
        assert result["datasetName"] in [d["first_dataset"].name, third_dataset.name]


def test_observations_json_combined_filters(public_api_data, client):
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1
    assert json_data["results"][0]["gbifId"] == "2"


def test_observations_json_combined_filters_case2(public_api_data, client):
    # Starting from test_observations_json_combined_filters, we add one dataset filter that won't change the results
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={yesterday.strftime('%Y-%m-%d')}&datasetsIds[]={d['second_dataset'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1
    assert json_data["results"][0]["gbifId"] == "2"


def test_observations_json_combined_filters_case3(public_api_data, client):
    # Starting from test_observations_json_combined_filters, we add one dataset filter => the filter combination now returns 0 results
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&datasetsIds[]={d['first_dataset'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 0


def test_observations_json_combined_filters_case4(public_api_data, client):
    # Starting from test_observations_json_combined_filters, we add one area filter that won't change the results
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&areaIds[]={d['public_area_lillois'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1


def test_observation_json_combined_filters_case5(public_api_data, client):
    # Starting from test_observations_json_combined_filters, we add one area filter => the filter combination now
    # returns 0 results
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&areaIds[]={d['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 0


def test_observation_json_combined_filters_case6(public_api_data, client):
    # Starting from test_observations_json_combined_filters, we also ask only unseen observations for another_user
    # => the filter combination now returns 0 results
    d = public_api_data
    client.login(username="frusciante1", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&status=unseen"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 0


def test_observation_json_combined_filters_case7(public_api_data, client):
    # Similar to test_observation_json_combined_filters_case6(), but with "seen" status. The single observation from
    # test_observation_json_combined_filters is seen, so that observation is still returned in this case
    d = public_api_data
    client.login(username="frusciante1", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['second_species'].pk}&endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&status=seen"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 1
    assert json_data["results"][0]["gbifId"] == "2"


def test_observations_json_no_results(public_api_data, client):
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-data-page")
    url_with_params = f"{base_url}?limit=10&page_number=1&speciesIds[]={d['first_species'].pk}&startDate={OCTOBER_8_2021.strftime('%Y-%m-%d')}"
    response = client.get(url_with_params)
    json_data = response.json()
    assert json_data["totalResultsCount"] == 0
    assert json_data["results"] == []


def test_observations_counter_no_filters(public_api_data, client):
    response = client.get(reverse("dashboard:public-api:filtered-observations-counter"))
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 3


def test_observations_counter_status_filter_case1(public_api_data, client):
    client.login(username="frusciante1", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?status=seen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1


def test_observations_counter_status_filter_case2(public_api_data, client):
    client.login(username="frusciante1", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?status=unseen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 2


def test_observations_counter_status_filter_case3(public_api_data, client):
    client.login(username="frusciante", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?status=seen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 0


def test_observations_counter_status_filter_case4(public_api_data, client):
    client.login(username="frusciante", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?status=unseen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 3


def test_observations_counter_status_filter_anonymous(public_api_data, client):
    """status is ignored for anonymous users"""
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?status=seen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 3


def test_observations_counter_status_filter_invalid(public_api_data, client):
    """status is ignored if not seen nor unseen"""
    client.login(username="frusciante", password="12345")
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?status=kvsnfgkdng"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 3


def test_observations_counter_species_filters(public_api_data, client):
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?speciesIds[]={d['second_species'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 2


def test_observation_counter_multiple_species_filter_case1(public_api_data, client):
    """We explicitly request all species: result should be identical to no species filtering"""
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    json_data_explicit = client.get(
        f"{base_url}?speciesIds[]={d['second_species'].pk}&speciesIds[]={d['first_species'].pk}"
    ).json()
    json_data_nofilters = client.get(f"{base_url}").json()
    assert json_data_explicit == json_data_nofilters


def test_observation_counter_multiple_species_filter_case2(public_api_data, client):
    """We add a third species and check we can ask a count for species 2 and 3 only"""
    d = public_api_data
    # We need one more species and related observations to perform this test
    species_tetraodon = Species.objects.create(
        name="Tetraodon fluviatilis", gbif_taxon_key=5213564
    )
    Observation.objects.create(
        gbif_id=1000,
        occurrence_id="1000",
        species=species_tetraodon,
        date=datetime.date.today(),
        data_import=d["di"],
        initial_data_import=d["di"],
        source_dataset=d["first_dataset"],
        basis_of_record=d["basis_of_record"],
    )
    Observation.objects.create(
        gbif_id=1001,
        occurrence_id="1001",
        species=species_tetraodon,
        date=datetime.date.today(),
        data_import=d["di"],
        initial_data_import=d["di"],
        source_dataset=d["first_dataset"],
        basis_of_record=d["basis_of_record"],
    )
    Observation.objects.create(
        gbif_id=1002,
        occurrence_id="1002",
        species=species_tetraodon,
        date=datetime.date.today(),
        data_import=d["di"],
        initial_data_import=d["di"],
        source_dataset=d["first_dataset"],
        basis_of_record=d["basis_of_record"],
    )

    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    json_data = client.get(
        f"{base_url}?speciesIds[]={d['second_species'].pk}&speciesIds[]={species_tetraodon.pk}"
    ).json()
    assert json_data["count"] == 5


def test_observations_counter_min_date_filter(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?startDate={OCTOBER_8_2021.strftime('%Y-%m-%d')}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1


def test_observations_counter_area_filter(public_api_data, client):
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?areaIds[]={d['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1


def test_observations_counter_max_date_filter(public_api_data, client):
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 2


def test_observations_counter_combined_filters(public_api_data, client):
    """Counter is correct when filtering by species and end date"""
    d = public_api_data
    base_url = reverse("dashboard:public-api:filtered-observations-counter")
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={d['second_species'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1

    # Case 2: we also add a dataset filter (which doesn't change the number of observations)
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={d['second_species'].pk}&datasetsIds[]={d['second_dataset'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1

    # Case 3: we add another one, which brings the counter to zero
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={d['second_species'].pk}&datasetsIds[]={d['first_dataset'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 0

    # Case 4: start from case 1) but add an area filter that brings us to zero records
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={d['second_species'].pk}&areaIds[]={d['public_area_andenne'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 0

    # Case 5: start from case 1) but add a status filter that brings un to zero records
    client.login(username="frusciante1", password="12345")
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={d['second_species'].pk}&status=unseen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 0

    # Case 6: similar to case 5), with seen status
    client.login(username="frusciante1", password="12345")
    url_with_params = f"{base_url}?endDate={SEPTEMBER_13_2021.strftime('%Y-%m-%d')}&speciesIds[]={d['second_species'].pk}&status=seen"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1


def test_observations_counter_basis_of_record_filter(public_api_data, client):
    """Counter is correct when filtering by basis of record"""
    d = public_api_data
    # Create a second basis of record and assign it to obs3
    machine_obs = BasisOfRecord.objects.create(name="MACHINE_OBSERVATION")
    d["obs3"].basis_of_record = machine_obs
    d["obs3"].save()

    base_url = reverse("dashboard:public-api:filtered-observations-counter")

    # Filter by HUMAN_OBSERVATION: obs1 + obs2 = 2
    url_with_params = f"{base_url}?basisOfRecordIds[]={d['basis_of_record'].pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 2

    # Filter by MACHINE_OBSERVATION: obs3 = 1
    url_with_params = f"{base_url}?basisOfRecordIds[]={machine_obs.pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 1

    # Filter by both: all 3 observations
    url_with_params = f"{base_url}?basisOfRecordIds[]={d['basis_of_record'].pk}&basisOfRecordIds[]={machine_obs.pk}"
    response = client.get(url_with_params)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["count"] == 3


def test_species_list_json(public_api_data, client):
    """Basic tests on the endpoint: status, length, content, ..."""
    response = client.get(reverse("dashboard:public-api:species-list-json"))
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"

    json_data = response.json()
    assert len(json_data) == 2

    # Check the main fields are there (no KeyError exception)
    json_data[0]["scientificName"]
    json_data[0]["id"]
    json_data[0]["gbifTaxonKey"]

    # Check a specific one can be found
    found = False
    for entry in json_data:
        if entry["scientificName"] == "Procambarus fallax":
            found = True
            break

    assert found


def test_species_list_cors_enabled(public_api_data, client):
    """Make sure CORS is enabled for the (semi public) species_list JSON API

    # Technique inspired from https://stackoverflow.com/a/47609921
    """
    request_headers = {
        "HTTP_ACCESS_CONTROL_REQUEST_METHOD": "GET",
        "HTTP_ORIGIN": "http://somethingelse.com",
    }
    response = client.get(
        reverse("dashboard:public-api:species-list-json"), {}, **request_headers
    )
    assert response.headers["Access-Control-Allow-Origin"] == "*"


@pytest.mark.parametrize(
    "name, query",
    [
        ("species-list-json", ""),
        ("filtered-observations-counter", ""),
        ("filtered-observations-data-page", "?limit=10&page_number=1"),
        ("species-per-polygon-json", "?p=POLYGON((4 50,5 50,5 51,4 51,4 50))"),
    ],
)
def test_legacy_endpoints_are_deprecated(public_api_data, client, name, query):
    """Each legacy /api JSON endpoint signals deprecation + a successor link."""
    resp = client.get(f"{reverse(f'dashboard:public-api:{name}')}{query}")
    assert resp.status_code == 200
    assert resp.headers.get("Deprecation") == "true"
    assert 'rel="successor-version"' in resp.headers.get("Link", "")
