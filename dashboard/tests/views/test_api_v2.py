import datetime
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse

from dashboard.models import (
    Alert,
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationComment,
    ObservationUnseen,
    Species,
)
from page_fragments.models import PageFragment

pytestmark = pytest.mark.django_db

# A minimal polygon - geometry is irrelevant for these tests.
SIMPLE_POLYGON = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)), srid=4326))

SAMPLE_DATA_DIR = Path(__file__).parent.parent / "various" / "sample_data"


# ---------------------------------------------------------------------------
# ApiV2FilterListsTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def filter_lists_data():
    """Fixture for the filter-lists tests (species, datasets, areas, basis-of-record, data-imports)."""
    User = get_user_model()

    area_owner = User.objects.create_user(
        username="area_owner", password="12345", email="area_owner@example.com"
    )
    other_user = User.objects.create_user(
        username="other_user", password="12345", email="other_user@example.com"
    )

    species = Species.objects.create(
        name="Procambarus fallax",
        vernacular_name="marbled crayfish",
        gbif_taxon_key=8879526,
    )
    species_no_tags = Species.objects.create(
        name="Orconectes virilis",
        vernacular_name="",
        gbif_taxon_key=2227064,
    )
    species.tags.add("invasive", "crustacean")

    dataset = Dataset.objects.create(
        name="Test dataset",
        gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
    )

    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")

    di = DataImport.objects.create(
        start=datetime.datetime(2024, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2024, 3, 15, 11, 0, 0, tzinfo=datetime.timezone.utc),
        completed=True,
    )

    public_area = Area.objects.create(name="Public area", mpoly=SIMPLE_POLYGON)
    user_area = Area.objects.create(
        name="User area", owner=area_owner, mpoly=SIMPLE_POLYGON
    )

    return {
        "area_owner": area_owner,
        "other_user": other_user,
        "species": species,
        "species_no_tags": species_no_tags,
        "dataset": dataset,
        "basis_of_record": basis_of_record,
        "di": di,
        "public_area": public_area,
        "user_area": user_area,
    }


# --- /api/v2/species/ ---


def test_species_list_status(client):
    response = client.get(reverse("api-v2:species_list"))
    assert response.status_code == 200


def test_species_list_camel_case_keys(client, filter_lists_data):
    """Field renames must produce camelCase JSON keys."""
    species = filter_lists_data["species"]
    response = client.get(reverse("api-v2:species_list"))
    species_data = [s for s in response.json() if s["id"] == species.pk]
    assert len(species_data) == 1
    entry = species_data[0]

    assert entry["id"] == species.pk
    assert entry["scientificName"] == "Procambarus fallax"
    assert entry["vernacularName"] == "marbled crayfish"
    assert entry["gbifTaxonKey"] == 8879526
    assert sorted(entry["tags"]) == sorted(["invasive", "crustacean"])


def test_species_list_empty_tags(client, filter_lists_data):
    """A species with no tags returns an empty list, not null."""
    species_no_tags = filter_lists_data["species_no_tags"]
    response = client.get(reverse("api-v2:species_list"))
    entry = next(s for s in response.json() if s["id"] == species_no_tags.pk)
    assert entry["tags"] == []


# --- /api/v2/datasets/ ---


def test_datasets_list_status(client):
    response = client.get(reverse("api-v2:datasets_list"))
    assert response.status_code == 200


def test_datasets_list_gbif_key_resolver(client, filter_lists_data):
    """gbifKey must be taken from Dataset.gbif_dataset_key, not a non-existent field."""
    dataset = filter_lists_data["dataset"]
    response = client.get(reverse("api-v2:datasets_list"))
    entry = next(d for d in response.json() if d["id"] == dataset.pk)

    assert entry["gbifKey"] == "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
    assert entry["name"] == "Test dataset"


# --- /api/v2/areas/ ---


def test_areas_list_anonymous_sees_only_public(client, filter_lists_data):
    public_area = filter_lists_data["public_area"]
    user_area = filter_lists_data["user_area"]
    response = client.get(reverse("api-v2:areas_list"))
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()]
    assert public_area.pk in ids
    assert user_area.pk not in ids


def test_areas_list_owner_sees_own_and_public(client, filter_lists_data):
    public_area = filter_lists_data["public_area"]
    user_area = filter_lists_data["user_area"]
    client.login(username="area_owner", password="12345")
    response = client.get(reverse("api-v2:areas_list"))
    ids = [a["id"] for a in response.json()]
    assert public_area.pk in ids
    assert user_area.pk in ids


def test_areas_list_other_user_sees_only_public(client, filter_lists_data):
    public_area = filter_lists_data["public_area"]
    user_area = filter_lists_data["user_area"]
    client.login(username="other_user", password="12345")
    response = client.get(reverse("api-v2:areas_list"))
    ids = [a["id"] for a in response.json()]
    assert public_area.pk in ids
    assert user_area.pk not in ids


def test_areas_list_is_user_specific_field(client, filter_lists_data):
    """isUserSpecific must reflect area ownership correctly."""
    public_area = filter_lists_data["public_area"]
    user_area = filter_lists_data["user_area"]
    client.login(username="area_owner", password="12345")
    response = client.get(reverse("api-v2:areas_list"))
    by_id = {a["id"]: a for a in response.json()}
    assert not by_id[public_area.pk]["isUserSpecific"]
    assert by_id[user_area.pk]["isUserSpecific"]


# --- /api/v2/basis-of-record/ ---


def test_basis_of_record_list_status(client):
    response = client.get(reverse("api-v2:basis_of_record_list"))
    assert response.status_code == 200


def test_basis_of_record_list_fields(client, filter_lists_data):
    basis_of_record = filter_lists_data["basis_of_record"]
    response = client.get(reverse("api-v2:basis_of_record_list"))
    entry = next(b for b in response.json() if b["id"] == basis_of_record.pk)
    assert entry["name"] == "HUMAN_OBSERVATION"


# --- /api/v2/data-imports/ ---


def test_data_imports_list_status(client):
    response = client.get(reverse("api-v2:data_imports_list"))
    assert response.status_code == 200


def test_data_imports_list_computed_name(client, filter_lists_data):
    """name is computed as 'Data import #N', not a model field."""
    di = filter_lists_data["di"]
    response = client.get(reverse("api-v2:data_imports_list"))
    entry = next(d for d in response.json() if d["id"] == di.pk)
    assert entry["name"] == f"Data import #{di.pk}"


def test_data_imports_list_start_timestamp(client, filter_lists_data):
    """startTimestamp is present and formatted as an ISO datetime string."""
    di = filter_lists_data["di"]
    response = client.get(reverse("api-v2:data_imports_list"))
    entry = next(d for d in response.json() if d["id"] == di.pk)
    assert entry["startTimestamp"] == "2024-03-15T10:00:00Z"


# ---------------------------------------------------------------------------
# ApiV2ObservationsTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def observations_data():
    """Fixture for the observations list tests."""
    User = get_user_model()
    user = User.objects.create_user(
        username="obs_user", password="12345", email="obs_user@example.com"
    )

    species = Species.objects.create(
        name="Procambarus fallax",
        vernacular_name="marbled crayfish",
        gbif_taxon_key=8879526,
    )
    other_species = Species.objects.create(
        name="Vespa velutina",
        vernacular_name="Asian hornet",
        gbif_taxon_key=1311477,
    )
    dataset = Dataset.objects.create(
        name="Test dataset",
        gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(
        start=datetime.datetime(2024, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
    )

    obs = Observation.objects.create(
        gbif_id="123",
        occurrence_id="occ:123",
        species=species,
        source_dataset=dataset,
        date=datetime.date(2024, 3, 10),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis_of_record,
        location=Point(4.35, 50.85, srid=4326),
    )
    obs_other_species = Observation.objects.create(
        gbif_id="456",
        occurrence_id="occ:456",
        species=other_species,
        source_dataset=dataset,
        date=datetime.date(2024, 3, 9),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis_of_record,
    )

    return {
        "user": user,
        "species": species,
        "other_species": other_species,
        "dataset": dataset,
        "basis_of_record": basis_of_record,
        "di": di,
        "obs": obs,
        "obs_other_species": obs_other_species,
    }


# --- Basic HTTP / shape ---


def test_observations_list_status(client):
    response = client.get(reverse("api-v2:observations_list"))
    assert response.status_code == 200


def test_observations_list_response_shape(client, observations_data):
    """Response must have 'count', 'speciesCount', 'datasetsCount', and 'items' at the top level."""
    response = client.get(reverse("api-v2:observations_list"))
    data = response.json()
    assert "count" in data
    assert "speciesCount" in data
    assert "datasetsCount" in data
    assert "items" in data
    assert isinstance(data["count"], int)
    assert isinstance(data["speciesCount"], int)
    assert isinstance(data["datasetsCount"], int)
    assert isinstance(data["items"], list)


def test_species_count_reflects_distinct_species(client, observations_data):
    """speciesCount must equal the number of distinct species in the result set."""
    response = client.get(reverse("api-v2:observations_list"))
    data = response.json()
    assert data["speciesCount"] == 2
    assert data["datasetsCount"] == 1


def test_species_count_respects_filters(client, observations_data):
    """speciesCount must drop when a species filter reduces the result set."""
    species = observations_data["species"]
    response = client.get(
        reverse("api-v2:observations_list"), {"speciesIds": species.pk}
    )
    data = response.json()
    assert data["speciesCount"] == 1
    assert data["datasetsCount"] == 1


def test_counts_are_zero_when_no_results(client, observations_data):
    """speciesCount and datasetsCount must both be 0 when the filter matches nothing."""
    response = client.get(reverse("api-v2:observations_list"), {"speciesIds": 999999})
    data = response.json()
    assert data["count"] == 0
    assert data["speciesCount"] == 0
    assert data["datasetsCount"] == 0


def test_observations_list_camel_case_keys(client, observations_data):
    """All expected camelCase keys must be present in each item."""
    obs = observations_data["obs"]
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs.pk)
    for key in (
        "id",
        "stableId",
        "gbifId",
        "lat",
        "lon",
        "scientificName",
        "vernacularName",
        "datasetName",
        "date",
        "municipality",
        "verified",
        "identificationVerificationStatus",
        "basisOfRecord",
    ):
        assert key in item, f"Missing key: {key}"


def test_observations_list_new_fields(client, observations_data):
    """municipality, verified, and identificationVerificationStatus must be present with correct values."""
    obs = observations_data["obs"]
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs.pk)
    assert item["municipality"] == ""
    assert item["verified"] is False
    assert item["identificationVerificationStatus"] == ""
    assert item["basisOfRecord"] == "HUMAN_OBSERVATION"


def test_observations_list_field_values(client, observations_data):
    """Field values must match the observation data."""
    obs = observations_data["obs"]
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs.pk)
    assert item["scientificName"] == "Procambarus fallax"
    assert item["vernacularName"] == "marbled crayfish"
    assert item["datasetName"] == "Test dataset"
    assert item["date"] == "2024-03-10"
    assert item["gbifId"] == "123"
    # lat/lon are present (location was set)
    assert item["lat"] is not None
    assert item["lon"] is not None


def test_observations_list_null_location(client, observations_data):
    """An observation without a location must return null lat and lon."""
    obs_other_species = observations_data["obs_other_species"]
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs_other_species.pk)
    assert item["lat"] is None
    assert item["lon"] is None


# --- seenByCurrentUser ---


def test_seen_by_current_user_is_null_for_anonymous(client, observations_data):
    """Anonymous users get null for seenByCurrentUser."""
    obs = observations_data["obs"]
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs.pk)
    assert item["seenByCurrentUser"] is None


def test_seen_by_current_user_true_when_no_unseen_record(client, observations_data):
    """Observation with no ObservationUnseen entry is considered seen."""
    obs = observations_data["obs"]
    client.login(username="obs_user", password="12345")
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs.pk)
    assert item["seenByCurrentUser"]


def test_seen_by_current_user_false_when_unseen_record_exists(
    client, observations_data
):
    """Observation with an ObservationUnseen entry is considered unseen."""
    obs = observations_data["obs"]
    user = observations_data["user"]
    ObservationUnseen.objects.create(observation=obs, user=user)
    client.login(username="obs_user", password="12345")
    response = client.get(reverse("api-v2:observations_list"))
    item = next(i for i in response.json()["items"] if i["id"] == obs.pk)
    assert not item["seenByCurrentUser"]


# --- Pagination ---


def test_pagination_count_reflects_total(client, observations_data):
    """count must reflect total matching observations, not just current page."""
    response = client.get(reverse("api-v2:observations_list"))
    assert response.json()["count"] == 2


def test_pagination_page_size_respected(client, observations_data):
    """pageSize=1 must return exactly 1 item."""
    response = client.get(
        reverse("api-v2:observations_list"), {"pageSize": 1, "page": 1}
    )
    data = response.json()
    assert len(data["items"]) == 1
    assert data["count"] == 2


def test_pagination_second_page(client, observations_data):
    """Page 2 with pageSize=1 returns the second observation."""
    response_p1 = client.get(
        reverse("api-v2:observations_list"), {"pageSize": 1, "page": 1}
    )
    response_p2 = client.get(
        reverse("api-v2:observations_list"), {"pageSize": 1, "page": 2}
    )
    id_p1 = response_p1.json()["items"][0]["id"]
    id_p2 = response_p2.json()["items"][0]["id"]
    assert id_p1 != id_p2


# --- Filter wiring ---


def test_species_filter(client, observations_data):
    """speciesIds filter must restrict results to matching observations."""
    species = observations_data["species"]
    obs = observations_data["obs"]
    response = client.get(
        reverse("api-v2:observations_list"), {"speciesIds": species.pk}
    )
    data = response.json()
    assert data["count"] == 1
    assert data["items"][0]["id"] == obs.pk


def test_observations_filter_by_dataset_ids(client, observations_data):
    """The v2 observations list filters on the renamed `datasetIds` query param."""
    dataset = observations_data["dataset"]
    # Both observations belong to this single dataset.
    matching = client.get(
        reverse("api-v2:observations_list"), {"datasetIds": dataset.pk}
    )
    assert matching.json()["count"] == 2
    # A non-existent dataset id matches nothing.
    none = client.get(reverse("api-v2:observations_list"), {"datasetIds": 999999})
    assert none.json()["count"] == 0


def test_observations_old_datasets_ids_param_is_ignored(client, observations_data):
    """The old misspelled `datasetsIds` param no longer filters (Ninja drops unknown params)."""
    all_count = client.get(reverse("api-v2:observations_list")).json()["count"]
    # The old name is unknown after the rename -> silently ignored, so the count
    # is unchanged rather than filtered down to a single dataset.
    resp = client.get(reverse("api-v2:observations_list"), {"datasetsIds": 999999})
    assert resp.json()["count"] == all_count


# ---------------------------------------------------------------------------
# ApiV2HistogramTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def histogram_data():
    """Fixture for the histogram endpoint tests."""
    species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    other_species = Species.objects.create(
        name="Vespa velutina", gbif_taxon_key=1311477
    )
    dataset = Dataset.objects.create(
        name="Test dataset",
        gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(
        start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    )
    # Two observations in different months
    obs_jan = Observation.objects.create(
        gbif_id="h1",
        occurrence_id="occ:h1",
        species=species,
        source_dataset=dataset,
        date=datetime.date(2024, 1, 15),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis_of_record,
    )
    obs_mar = Observation.objects.create(
        gbif_id="h2",
        occurrence_id="occ:h2",
        species=species,
        source_dataset=dataset,
        date=datetime.date(2024, 3, 10),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis_of_record,
    )
    obs_other_species = Observation.objects.create(
        gbif_id="h3",
        occurrence_id="occ:h3",
        species=other_species,
        source_dataset=dataset,
        date=datetime.date(2024, 2, 5),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis_of_record,
    )

    return {
        "species": species,
        "other_species": other_species,
        "dataset": dataset,
        "basis_of_record": basis_of_record,
        "di": di,
        "obs_jan": obs_jan,
        "obs_mar": obs_mar,
        "obs_other_species": obs_other_species,
    }


def test_histogram_status(client):
    response = client.get(reverse("api-v2:observations_histogram"))
    assert response.status_code == 200


def test_histogram_response_is_list(client):
    response = client.get(reverse("api-v2:observations_histogram"))
    assert isinstance(response.json(), list)


def test_histogram_entry_shape(client, histogram_data):
    """Each entry must have year, month, count keys."""
    response = client.get(reverse("api-v2:observations_histogram"))
    for entry in response.json():
        assert "year" in entry
        assert "month" in entry
        assert "count" in entry


def test_histogram_chronological_order(client, histogram_data):
    """Entries must be in ascending chronological order."""
    response = client.get(reverse("api-v2:observations_histogram"))
    entries = response.json()
    dates = [(e["year"], e["month"]) for e in entries]
    assert dates == sorted(dates)


def test_histogram_counts_by_month(client, histogram_data):
    """Each month must report the correct observation count."""
    response = client.get(reverse("api-v2:observations_histogram"))
    by_month = {(e["year"], e["month"]): e["count"] for e in response.json()}
    assert by_month[(2024, 1)] == 1
    assert by_month[(2024, 2)] == 1
    assert by_month[(2024, 3)] == 1


def test_histogram_respects_date_filters(client, histogram_data):
    """startDate/endDate params must restrict which observations are counted."""
    # Exclude January by starting from February
    response = client.get(
        reverse("api-v2:observations_histogram"),
        {"startDate": "2024-02-01", "endDate": "2024-12-31"},
    )
    by_month = {(e["year"], e["month"]): e["count"] for e in response.json()}
    assert (2024, 1) not in by_month
    assert (2024, 2) in by_month
    assert by_month[(2024, 2)] == 1


def test_histogram_species_filter(client, histogram_data):
    """speciesIds filter must restrict which observations are counted."""
    species = histogram_data["species"]
    response = client.get(
        reverse("api-v2:observations_histogram"),
        {"speciesIds": species.pk},
    )
    by_month = {(e["year"], e["month"]): e["count"] for e in response.json()}
    # February only has obs_other_species, so it should be absent or 0
    assert (2024, 2) not in by_month


# ---------------------------------------------------------------------------
# ApiV2ObservationsSortingTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sorting_data():
    """Fixture for the observations sorting tests."""
    species_alpha = Species.objects.create(
        name="Anas platyrhynchos",
        gbif_taxon_key=2498252,
        vernacular_name_en="Mallard",  # alphabetically AFTER Common pochard
        vernacular_name_fr="Canard colvert",
    )
    species_zeta = Species.objects.create(
        name="Zeta vulgaris",
        gbif_taxon_key=9999999,
        vernacular_name_en="Common pochard",  # alphabetically BEFORE Mallard
        vernacular_name_fr="Fuligule milouin",
    )
    dataset_alpha = Dataset.objects.create(
        name="Alpha dataset",
        gbif_dataset_key="aaaaaaaa-0000-0000-0000-000000000001",
    )
    dataset_zeta = Dataset.objects.create(
        name="Zeta dataset",
        gbif_dataset_key="zzzzzzzz-0000-0000-0000-000000000002",
    )
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(
        start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    )
    obs_alpha = Observation.objects.create(
        gbif_id="sort1",
        occurrence_id="occ:sort1",
        species=species_alpha,
        source_dataset=dataset_alpha,
        date=datetime.date(2024, 1, 1),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis,
    )
    obs_zeta = Observation.objects.create(
        gbif_id="sort2",
        occurrence_id="occ:sort2",
        species=species_zeta,
        source_dataset=dataset_zeta,
        date=datetime.date(2024, 6, 15),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis,
    )

    return {
        "species_alpha": species_alpha,
        "species_zeta": species_zeta,
        "dataset_alpha": dataset_alpha,
        "dataset_zeta": dataset_zeta,
        "basis": basis,
        "di": di,
        "obs_alpha": obs_alpha,
        "obs_zeta": obs_zeta,
    }


def _sorting_ids(client, **params):
    """Return the ordered list of observation ids from a GET request."""
    response = client.get(reverse("api-v2:observations_list"), params)
    assert response.status_code == 200
    return [item["id"] for item in response.json()["items"]]


# --- date ---


def test_default_order_is_date_descending(client, sorting_data):
    """With no sort params the newest observation must come first."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client)
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


def test_order_by_date_descending_explicit(client, sorting_data):
    """orderBy=date&orderDir=desc puts the newest observation first."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="date", orderDir="desc")
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


def test_order_by_date_ascending(client, sorting_data):
    """orderBy=date&orderDir=asc puts the oldest observation first."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="date", orderDir="asc")
    assert ids.index(obs_alpha.pk) < ids.index(obs_zeta.pk)


# --- scientificName ---


def test_order_by_scientific_name_ascending(client, sorting_data):
    """orderBy=scientificName&orderDir=asc puts Anas before Zeta."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="scientificName", orderDir="asc")
    assert ids.index(obs_alpha.pk) < ids.index(obs_zeta.pk)


def test_order_by_scientific_name_descending(client, sorting_data):
    """orderBy=scientificName&orderDir=desc puts Zeta before Anas."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="scientificName", orderDir="desc")
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


# --- vernacularName ---


def test_order_by_vernacular_name_ascending_uses_active_locale(client, sorting_data):
    """orderBy=vernacularName&orderDir=asc orders by the request's active vernacular locale.

    species_zeta has English vernacular 'Common pochard' (sorts BEFORE);
    species_alpha has 'Mallard' (sorts AFTER). Default test locale is 'en'.
    """
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="vernacularName", orderDir="asc")
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


def test_order_by_vernacular_name_descending(client, sorting_data):
    """orderBy=vernacularName&orderDir=desc reverses the asc order."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="vernacularName", orderDir="desc")
    assert ids.index(obs_alpha.pk) < ids.index(obs_zeta.pk)


def test_order_by_vernacular_name_falls_back_to_scientific_when_missing(
    client, sorting_data
):
    """When a species has no vernacular in the active locale, the scientific name
    is used as the sort key instead.

    We empty species_alpha's English vernacular ('Mallard') and re-fetch in 'en'.
    Now species_alpha's effective sort key is 'Anas platyrhynchos' (its scientific
    name, alphabetically before species_zeta's 'Common pochard'), so obs_alpha
    sorts first.
    """
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    species_alpha = sorting_data["species_alpha"]
    species_alpha.vernacular_name_en = ""
    species_alpha.save()

    ids = _sorting_ids(client, orderBy="vernacularName", orderDir="asc")
    assert ids.index(obs_alpha.pk) < ids.index(obs_zeta.pk)


def test_order_by_vernacular_name_uses_french_when_lang_is_french(client, sorting_data):
    """Switching the request locale to French changes the vernacular column used.

    species_alpha FR vernacular: 'Canard colvert' (sorts BEFORE);
    species_zeta  FR vernacular: 'Fuligule milouin' (sorts AFTER).
    Opposite of the English order asserted in test_order_by_vernacular_name_ascending_uses_active_locale.
    """
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]

    response = client.get(
        reverse("api-v2:observations_list"),
        {"orderBy": "vernacularName", "orderDir": "asc"},
        HTTP_ACCEPT_LANGUAGE="fr",
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids.index(obs_alpha.pk) < ids.index(obs_zeta.pk)


# --- datasetName ---


def test_order_by_dataset_name_ascending(client, sorting_data):
    """orderBy=datasetName&orderDir=asc puts Alpha dataset before Zeta dataset."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="datasetName", orderDir="asc")
    assert ids.index(obs_alpha.pk) < ids.index(obs_zeta.pk)


def test_order_by_dataset_name_descending(client, sorting_data):
    """orderBy=datasetName&orderDir=desc puts Zeta dataset before Alpha dataset."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="datasetName", orderDir="desc")
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


# --- robustness ---


def test_unknown_order_by_falls_back_to_date(client, sorting_data):
    """An unrecognised orderBy value must not crash - falls back to date sort."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    response = client.get(
        reverse("api-v2:observations_list"), {"orderBy": "nonExistentField"}
    )
    assert response.status_code == 200
    # Default date-desc order: obs_zeta (newer) before obs_alpha (older)
    ids = [item["id"] for item in response.json()["items"]]
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


def test_unknown_order_dir_treated_as_desc(client, sorting_data):
    """Any orderDir value other than 'asc' must be treated as descending."""
    obs_alpha = sorting_data["obs_alpha"]
    obs_zeta = sorting_data["obs_zeta"]
    ids = _sorting_ids(client, orderBy="date", orderDir="INVALID")
    assert ids.index(obs_zeta.pk) < ids.index(obs_alpha.pk)


# ---------------------------------------------------------------------------
# ApiV2ObservationDetailTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def observation_detail_data():
    """Fixture for the observation detail endpoint tests."""
    User = get_user_model()
    user = User.objects.create_user(
        username="detail_user", password="12345", email="detail_user@example.com"
    )
    commenter = User.objects.create_user(
        username="commenter", password="12345", email="commenter@example.com"
    )

    species = Species.objects.create(
        name="Harmonia axyridis",
        vernacular_name="harlequin ladybird",
        gbif_taxon_key=1234567,
    )
    dataset = Dataset.objects.create(
        name="Detail dataset",
        gbif_dataset_key="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(
        start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    )
    obs = Observation.objects.create(
        gbif_id="999",
        occurrence_id="occ:999",
        species=species,
        source_dataset=dataset,
        date=datetime.date(2024, 5, 1),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis_of_record,
        location=Point(4.35, 50.85, srid=4326),
    )

    return {
        "user": user,
        "commenter": commenter,
        "species": species,
        "dataset": dataset,
        "basis_of_record": basis_of_record,
        "di": di,
        "obs": obs,
    }


# --- Basic HTTP / shape ---


def test_detail_404_for_unknown_stable_id(client):
    response = client.get("/api/v2/observations/nonexistent/")
    assert response.status_code == 404


def test_detail_status_200(client, observation_detail_data):
    obs = observation_detail_data["obs"]
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    assert response.status_code == 200


def test_detail_camel_case_keys(client, observation_detail_data):
    """All expected camelCase keys must be present in the response."""
    obs = observation_detail_data["obs"]
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    data = response.json()
    for key in (
        "id",
        "stableId",
        "gbifId",
        "lat",
        "lon",
        "scientificName",
        "vernacularName",
        "datasetName",
        "datasetGbifKey",
        "date",
        "basisOfRecord",
        "seenByCurrentUser",
        "canBeMarkedUnseen",
        "comments",
    ):
        assert key in data, f"Missing key: {key}"


def test_detail_field_values(client, observation_detail_data):
    obs = observation_detail_data["obs"]
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    data = response.json()
    assert data["stableId"] == obs.stable_id
    assert data["scientificName"] == "Harmonia axyridis"
    assert data["vernacularName"] == "harlequin ladybird"
    assert data["datasetName"] == "Detail dataset"
    assert data["date"] == "2024-05-01"


# --- canBeMarkedUnseen ---


def test_can_be_marked_unseen_false_for_anonymous(client, observation_detail_data):
    obs = observation_detail_data["obs"]
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    assert not response.json()["canBeMarkedUnseen"]


def test_can_be_marked_unseen_false_when_no_matching_alert(
    client, observation_detail_data
):
    """Authenticated user with no alerts: cannot mark unseen."""
    obs = observation_detail_data["obs"]
    user = observation_detail_data["user"]
    client.force_login(user)
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    assert not response.json()["canBeMarkedUnseen"]


def test_can_be_marked_unseen_true_when_alert_matches(client, observation_detail_data):
    """Authenticated user with a matching alert: can mark unseen."""
    obs = observation_detail_data["obs"]
    user = observation_detail_data["user"]
    client.force_login(user)
    alert = Alert.objects.create(
        user=user, email_notifications_frequency=Alert.DAILY_EMAILS
    )
    alert.species.add(obs.species)
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    assert response.json()["canBeMarkedUnseen"]


# --- comments ---


def test_comments_returned_with_author_username(client, observation_detail_data):
    """Comments list must include the author's username."""
    obs = observation_detail_data["obs"]
    commenter = observation_detail_data["commenter"]
    ObservationComment.objects.create(
        observation=obs, author=commenter, text="Nice find!"
    )
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    comments = response.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["authorUsername"] == "commenter"
    assert comments[0]["text"] == "Nice find!"


def test_comments_empty_list_when_none(client, observation_detail_data):
    obs = observation_detail_data["obs"]
    response = client.get(f"/api/v2/observations/{obs.stable_id}/")
    assert response.json()["comments"] == []


def test_observation_add_comment_anonymous_returns_401(client, observation_detail_data):
    """Anonymous users may not post comments. They get 401, not 403."""
    obs = observation_detail_data["obs"]
    resp = client.post(
        f"/api/v2/observations/{obs.stable_id}/comments/",
        data={"text": "Anonymous attempt"},
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_observation_mark_unseen_anonymous_returns_401(client, observation_detail_data):
    """Anonymous users get 401 from mark-unseen, not 403."""
    obs = observation_detail_data["obs"]
    resp = client.post(f"/api/v2/observations/{obs.stable_id}/mark-unseen/")
    assert resp.status_code == 401


def test_observation_mark_unseen_no_matching_alert_returns_403(
    client, observation_detail_data
):
    """Authenticated user with no matching alert cannot mark unseen: 403."""
    user = observation_detail_data["user"]
    obs = observation_detail_data["obs"]
    client.force_login(user)
    resp = client.post(f"/api/v2/observations/{obs.stable_id}/mark-unseen/")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# ApiV2ObservationsMunicipalityVerifiedSortTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def municipality_sort_data():
    """Fixture for the municipality/verified sorting tests."""
    species = Species.objects.create(name="Testus sorticus", gbif_taxon_key=9990001)
    dataset = Dataset.objects.create(
        name="Sort test dataset",
        gbif_dataset_key="11111111-0000-0000-0000-000000000099",
    )
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(
        start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    )
    obs_gent = Observation.objects.create(
        gbif_id="munis1",
        occurrence_id="occ:munis1",
        species=species,
        source_dataset=dataset,
        date=datetime.date(2024, 1, 1),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis,
        municipality="Gent",
        verified=True,
    )
    obs_mons = Observation.objects.create(
        gbif_id="munis2",
        occurrence_id="occ:munis2",
        species=species,
        source_dataset=dataset,
        date=datetime.date(2024, 1, 2),
        data_import=di,
        initial_data_import=di,
        basis_of_record=basis,
        municipality="Mons",
        verified=False,
    )

    return {
        "species": species,
        "dataset": dataset,
        "basis": basis,
        "di": di,
        "obs_gent": obs_gent,
        "obs_mons": obs_mons,
    }


def _municipality_ids(client, **params):
    """Return the ordered list of observation ids from a GET request."""
    response = client.get(reverse("api-v2:observations_list"), params)
    assert response.status_code == 200
    return [item["id"] for item in response.json()["items"]]


def test_order_by_municipality_ascending(client, municipality_sort_data):
    """orderBy=municipality&orderDir=asc puts Gent before Mons."""
    obs_gent = municipality_sort_data["obs_gent"]
    obs_mons = municipality_sort_data["obs_mons"]
    ids = _municipality_ids(client, orderBy="municipality", orderDir="asc")
    assert ids.index(obs_gent.pk) < ids.index(obs_mons.pk)


def test_order_by_municipality_descending(client, municipality_sort_data):
    """orderBy=municipality&orderDir=desc puts Mons before Gent."""
    obs_gent = municipality_sort_data["obs_gent"]
    obs_mons = municipality_sort_data["obs_mons"]
    ids = _municipality_ids(client, orderBy="municipality", orderDir="desc")
    assert ids.index(obs_mons.pk) < ids.index(obs_gent.pk)


def test_order_by_verified_ascending(client, municipality_sort_data):
    """orderBy=verified&orderDir=asc puts False (obs_mons) before True (obs_gent)."""
    obs_gent = municipality_sort_data["obs_gent"]
    obs_mons = municipality_sort_data["obs_mons"]
    ids = _municipality_ids(client, orderBy="verified", orderDir="asc")
    assert ids.index(obs_mons.pk) < ids.index(obs_gent.pk)


def test_order_by_verified_descending(client, municipality_sort_data):
    """orderBy=verified&orderDir=desc puts True (obs_gent) before False (obs_mons)."""
    obs_gent = municipality_sort_data["obs_gent"]
    obs_mons = municipality_sort_data["obs_mons"]
    ids = _municipality_ids(client, orderBy="verified", orderDir="desc")
    assert ids.index(obs_gent.pk) < ids.index(obs_mons.pk)


# ---------------------------------------------------------------------------
# ApiV2AlertTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def alert_data():
    """Fixture for the alerts CRUD endpoint tests."""
    User = get_user_model()
    user = User.objects.create_user(
        username="alertuser", password="12345", email="alert@example.com"
    )
    other_user = User.objects.create_user(
        username="otheruser", password="12345", email="other@example.com"
    )
    sp1 = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    sp2 = Species.objects.create(name="Orconectes virilis", gbif_taxon_key=2227064)
    alert = Alert.objects.create(
        name="My alert #1", user=user, email_notifications_frequency="N"
    )
    alert.species.add(sp1)

    return {
        "user": user,
        "other_user": other_user,
        "sp1": sp1,
        "sp2": sp2,
        "alert": alert,
    }


# --- /api/v2/alerts/ (list) ---


def test_alerts_list_requires_auth(client):
    response = client.get("/api/v2/alerts/")
    assert response.status_code == 401


def test_alerts_list_returns_own_alerts(client, alert_data):
    client.login(username="alertuser", password="12345")
    response = client.get("/api/v2/alerts/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "My alert #1"
    assert "speciesIds" in data[0]
    assert "unseenCount" in data[0]


def test_alerts_list_does_not_include_other_users_alerts(client, alert_data):
    other_user = alert_data["other_user"]
    sp1 = alert_data["sp1"]
    other_alert = Alert.objects.create(
        name="Other alert", user=other_user, email_notifications_frequency="N"
    )
    other_alert.species.add(sp1)
    client.login(username="alertuser", password="12345")
    response = client.get("/api/v2/alerts/")
    assert len(response.json()) == 1


# --- POST /api/v2/alerts/ (create) ---


def test_alert_create_success(client, alert_data):
    user = alert_data["user"]
    sp1 = alert_data["sp1"]
    client.login(username="alertuser", password="12345")
    payload = json.dumps({"name": "New alert", "speciesIds": [sp1.pk]})
    response = client.post("/api/v2/alerts/", payload, content_type="application/json")
    assert response.status_code == 201
    assert Alert.objects.filter(name="New alert", user=user).exists()


def test_alert_create_no_species_returns_422(client, alert_data):
    client.login(username="alertuser", password="12345")
    payload = json.dumps({"name": "Bad alert", "speciesIds": []})
    response = client.post("/api/v2/alerts/", payload, content_type="application/json")
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == "Validation failed"
    assert "species" in data["errors"]


def test_alert_create_requires_auth(client, alert_data):
    sp1 = alert_data["sp1"]
    payload = json.dumps({"name": "Unauth alert", "speciesIds": [sp1.pk]})
    response = client.post("/api/v2/alerts/", payload, content_type="application/json")
    assert response.status_code == 401


# --- GET /api/v2/alerts/{alert_id}/ (detail) ---


def test_alert_detail_returns_correct_fields(client, alert_data):
    alert = alert_data["alert"]
    sp1 = alert_data["sp1"]
    client.login(username="alertuser", password="12345")
    response = client.get(f"/api/v2/alerts/{alert.pk}/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My alert #1"
    assert data["speciesIds"] == [sp1.pk]
    assert "speciesList" in data
    assert "emailNotificationsFrequencyDisplay" in data


def test_alert_detail_wrong_user_returns_404(client, alert_data):
    alert = alert_data["alert"]
    client.login(username="otheruser", password="12345")
    response = client.get(f"/api/v2/alerts/{alert.pk}/")
    assert response.status_code == 404


# --- PUT /api/v2/alerts/{alert_id}/ (update) ---


def test_alert_update_success(client, alert_data):
    alert = alert_data["alert"]
    sp1 = alert_data["sp1"]
    sp2 = alert_data["sp2"]
    client.login(username="alertuser", password="12345")
    payload = json.dumps({"name": "Renamed alert", "speciesIds": [sp1.pk, sp2.pk]})
    response = client.put(
        f"/api/v2/alerts/{alert.pk}/", payload, content_type="application/json"
    )
    assert response.status_code == 200
    alert.refresh_from_db()
    assert alert.name == "Renamed alert"
    assert alert.species.count() == 2


def test_alert_update_wrong_user_returns_404(client, alert_data):
    alert = alert_data["alert"]
    sp1 = alert_data["sp1"]
    client.login(username="otheruser", password="12345")
    payload = json.dumps({"name": "Hacked", "speciesIds": [sp1.pk]})
    response = client.put(
        f"/api/v2/alerts/{alert.pk}/", payload, content_type="application/json"
    )
    assert response.status_code == 404


# --- DELETE /api/v2/alerts/{alert_id}/ ---


def test_alert_delete_success(client, alert_data):
    user = alert_data["user"]
    sp1 = alert_data["sp1"]
    to_delete = Alert.objects.create(
        name="To delete", user=user, email_notifications_frequency="N"
    )
    to_delete.species.add(sp1)
    client.login(username="alertuser", password="12345")
    response = client.delete(f"/api/v2/alerts/{to_delete.pk}/")
    assert response.status_code == 204
    assert not Alert.objects.filter(pk=to_delete.pk).exists()


def test_alert_delete_wrong_user_returns_404(client, alert_data):
    alert = alert_data["alert"]
    client.login(username="otheruser", password="12345")
    response = client.delete(f"/api/v2/alerts/{alert.pk}/")
    assert response.status_code == 404
    assert Alert.objects.filter(pk=alert.pk).exists()


# --- GET /api/v2/spa/alerts/suggest-name/ ---


def test_suggest_name_returns_first_available(client, alert_data):
    # "My alert #1" is taken; next should be "My alert #2"
    client.login(username="alertuser", password="12345")
    response = client.get("/api/v2/spa/alerts/suggest-name/")
    assert response.status_code == 200
    assert response.json()["name"] == "My alert #2"


# --- GET /api/v2/alerts/notification-frequencies/ ---


def test_notification_frequencies_list(client):
    response = client.get("/api/v2/alerts/notification-frequencies/")
    assert response.status_code == 200
    data = response.json()
    ids = [f["id"] for f in data]
    assert "N" in ids
    assert "D" in ids
    assert "W" in ids
    assert "M" in ids


def test_alert_create_duplicate_name_returns_422(client, alert_data):
    """Creating an alert with a name already owned by this user returns 422."""
    sp1 = alert_data["sp1"]
    client.login(username="alertuser", password="12345")
    # "My alert #1" already exists in alert_data
    payload = json.dumps({"name": "My alert #1", "speciesIds": [sp1.pk]})
    response = client.post("/api/v2/alerts/", payload, content_type="application/json")
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == "Validation failed"
    assert "errors" in data


def test_alert_create_approaching_mode_without_area_returns_422(client, alert_data):
    """Creating an alert with areaFilterMode='approaching' but no areaIds returns 422."""
    sp1 = alert_data["sp1"]
    client.login(username="alertuser", password="12345")
    payload = json.dumps(
        {
            "name": "Approaching alert",
            "speciesIds": [sp1.pk],
            "areaFilterMode": "approaching",
            "areaIds": [],
        }
    )
    response = client.post("/api/v2/alerts/", payload, content_type="application/json")
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == "Validation failed"
    assert "area_filter_mode" in data["errors"]


# ---------------------------------------------------------------------------
# ApiV2AreaEndpointsTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def area_endpoints_data():
    """Fixture for the area CRUD/GeoJSON endpoint tests."""
    User = get_user_model()
    owner = User.objects.create_user(
        username="owner", password="pass", email="owner@example.com"
    )
    other = User.objects.create_user(
        username="other", password="pass", email="other@example.com"
    )
    area = Area.objects.create(
        name="My area",
        owner=owner,
        mpoly=SIMPLE_POLYGON,
    )

    return {
        "owner": owner,
        "other": other,
        "area": area,
    }


# --- GET /api/v2/areas/{id}/geojson/ ---


def test_geojson_returns_200_for_owner(client, area_endpoints_data):
    area = area_endpoints_data["area"]
    client.login(username="owner", password="pass")
    response = client.get(f"/api/v2/areas/{area.pk}/geojson/")
    assert response.status_code == 200


def test_geojson_returns_geojson_content_type(client, area_endpoints_data):
    area = area_endpoints_data["area"]
    client.login(username="owner", password="pass")
    response = client.get(f"/api/v2/areas/{area.pk}/geojson/")
    assert "application/json" in response.get("Content-Type", "")


def test_geojson_body_is_feature_collection(client, area_endpoints_data):
    area = area_endpoints_data["area"]
    client.login(username="owner", password="pass")
    response = client.get(f"/api/v2/areas/{area.pk}/geojson/")
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1


def test_geojson_returns_403_for_unrelated_user(client, area_endpoints_data):
    """User cannot fetch GeoJSON for another user's private area."""
    area = area_endpoints_data["area"]
    client.login(username="other", password="pass")
    response = client.get(f"/api/v2/areas/{area.pk}/geojson/")
    assert response.status_code == 403


def test_geojson_returns_404_for_nonexistent(client, area_endpoints_data):
    client.login(username="owner", password="pass")
    response = client.get("/api/v2/areas/99999/geojson/")
    assert response.status_code == 404


# --- POST /api/v2/areas/ ---


def test_create_area_returns_201(client, area_endpoints_data):
    client.login(username="owner", password="pass")
    gpkg = SAMPLE_DATA_DIR / "polygon_4326.gpkg"
    with open(gpkg, "rb") as f:
        response = client.post(
            "/api/v2/areas/",
            {"name": "New area", "data_file": f},
        )
    assert response.status_code == 201


def test_create_area_persists_in_db(client, area_endpoints_data):
    owner = area_endpoints_data["owner"]
    client.login(username="owner", password="pass")
    gpkg = SAMPLE_DATA_DIR / "polygon_4326.gpkg"
    with open(gpkg, "rb") as f:
        client.post("/api/v2/areas/", {"name": "Persisted area", "data_file": f})
    assert Area.objects.filter(name="Persisted area", owner=owner).exists()


def test_create_area_response_shape(client, area_endpoints_data):
    client.login(username="owner", password="pass")
    gpkg = SAMPLE_DATA_DIR / "polygon_4326.gpkg"
    with open(gpkg, "rb") as f:
        response = client.post(
            "/api/v2/areas/",
            {"name": "Shape test", "data_file": f},
        )
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "isUserSpecific" in data
    assert data["isUserSpecific"]


def test_create_area_wrong_geometry_returns_422(client, area_endpoints_data):
    """Uploading a point GeoPackage (wrong geometry type) returns 422."""
    client.login(username="owner", password="pass")
    gpkg = SAMPLE_DATA_DIR / "point.gpkg"
    with open(gpkg, "rb") as f:
        response = client.post("/api/v2/areas/", {"name": "Bad", "data_file": f})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_area_too_many_features_returns_422(client, area_endpoints_data):
    client.login(username="owner", password="pass")
    gpkg = SAMPLE_DATA_DIR / "polygon_4326_too_many_features.gpkg"
    with open(gpkg, "rb") as f:
        response = client.post("/api/v2/areas/", {"name": "Bad", "data_file": f})
    assert response.status_code == 422


def test_create_area_requires_authentication(client):
    gpkg = SAMPLE_DATA_DIR / "polygon_4326.gpkg"
    with open(gpkg, "rb") as f:
        response = client.post("/api/v2/areas/", {"name": "Unauth", "data_file": f})
    assert response.status_code == 401


# --- DELETE /api/v2/areas/{id}/ ---


def test_delete_area_returns_204(client, area_endpoints_data):
    owner = area_endpoints_data["owner"]
    area = Area.objects.create(name="To delete", owner=owner, mpoly=SIMPLE_POLYGON)
    client.login(username="owner", password="pass")
    response = client.delete(f"/api/v2/areas/{area.pk}/")
    assert response.status_code == 204


def test_delete_area_removes_from_db(client, area_endpoints_data):
    owner = area_endpoints_data["owner"]
    area = Area.objects.create(name="Gone", owner=owner, mpoly=SIMPLE_POLYGON)
    client.login(username="owner", password="pass")
    client.delete(f"/api/v2/areas/{area.pk}/")
    assert not Area.objects.filter(pk=area.pk).exists()


def test_delete_area_returns_404_for_nonexistent(client, area_endpoints_data):
    client.login(username="owner", password="pass")
    response = client.delete("/api/v2/areas/99999/")
    assert response.status_code == 404


def test_delete_area_returns_404_for_other_user_area(client, area_endpoints_data):
    """Cannot delete another user's area."""
    other = area_endpoints_data["other"]
    area = Area.objects.create(name="Other's", owner=other, mpoly=SIMPLE_POLYGON)
    client.login(username="owner", password="pass")
    response = client.delete(f"/api/v2/areas/{area.pk}/")
    assert response.status_code == 404


def test_delete_area_with_alert_returns_409(client, area_endpoints_data):
    """Area referenced by an alert returns 409 with a detail message."""
    owner = area_endpoints_data["owner"]
    area = Area.objects.create(name="Has alert", owner=owner, mpoly=SIMPLE_POLYGON)
    sp = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    alert = Alert.objects.create(
        name="Alert", user=owner, email_notifications_frequency="N"
    )
    alert.species.add(sp)
    alert.areas.add(area)

    client.login(username="owner", password="pass")
    response = client.delete(f"/api/v2/areas/{area.pk}/")
    assert response.status_code == 409
    assert "detail" in response.json()
    assert Area.objects.filter(pk=area.pk).exists()


def test_delete_area_requires_authentication(client, area_endpoints_data):
    area = area_endpoints_data["area"]
    response = client.delete(f"/api/v2/areas/{area.pk}/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# ApiV2AuthTests fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_data():
    """Fixture for the auth endpoint tests."""
    User = get_user_model()
    user = User.objects.create_user(
        username="testuser",
        password="correctpassword",
        email="test@example.com",
    )
    return {"user": user}


# --- signin ---


def test_signin_success(client, auth_data):
    resp = client.post(
        "/api/v2/auth/signin/",
        data={"username": "testuser", "password": "correctpassword"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


def test_signin_wrong_password(client, auth_data):
    resp = client.post(
        "/api/v2/auth/signin/",
        data={"username": "testuser", "password": "wrong"},
        content_type="application/json",
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_signin_nonexistent_user(client):
    resp = client.post(
        "/api/v2/auth/signin/",
        data={"username": "nobody", "password": "x"},
        content_type="application/json",
    )
    assert resp.status_code == 401


# --- signup ---


def test_signup_success(client):
    User = get_user_model()
    resp = client.post(
        "/api/v2/auth/signup/",
        data={
            "username": "newuser",
            "email": "new@example.com",
            "language": "en",
            "password1": "Secure1234!",
            "password2": "Secure1234!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"
    assert User.objects.filter(username="newuser").exists()


def test_signup_duplicate_username(client, auth_data):
    resp = client.post(
        "/api/v2/auth/signup/",
        data={
            "username": "testuser",  # already exists
            "email": "other@example.com",
            "language": "en",
            "password1": "Secure1234!",
            "password2": "Secure1234!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Validation failed"
    assert "username" in resp.json()["errors"]


def test_signup_password_mismatch(client):
    resp = client.post(
        "/api/v2/auth/signup/",
        data={
            "username": "anotheruser",
            "email": "a@example.com",
            "language": "en",
            "password1": "Secure1234!",
            "password2": "Different!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Validation failed"
    assert "errors" in resp.json()


def test_signup_camelcase_names_persisted(client):
    """Signup accepts firstName/lastName and persists them to the user."""
    User = get_user_model()
    resp = client.post(
        "/api/v2/auth/signup/",
        data={
            "username": "cameluser",
            "firstName": "Ada",
            "lastName": "Lovelace",
            "email": "ada@example.com",
            "language": "en",
            "password1": "Secure1234!",
            "password2": "Secure1234!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 201
    u = User.objects.get(username="cameluser")
    assert u.first_name == "Ada"
    assert u.last_name == "Lovelace"


def test_signup_validation_errors_use_camelcase_keys(client, auth_data):
    """A signup failure returns error keys in the API's camelCase names, not Django's."""
    # Duplicate username forces a form error; ensure no snake_case name leaks.
    resp = client.post(
        "/api/v2/auth/signup/",
        data={
            "username": "testuser",  # already exists (auth_data fixture)
            "firstName": "X",
            "lastName": "Y",
            "email": "x@example.com",
            "language": "en",
            "password1": "Secure1234!",
            "password2": "Secure1234!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    keys = resp.json()["errors"].keys()
    assert "first_name" not in keys
    assert "last_name" not in keys


# --- password-change ---


def test_password_change_success(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.post(
        "/api/v2/auth/password-change/",
        data={
            "oldPassword": "correctpassword",
            "newPassword1": "NewSecure5678!",
            "newPassword2": "NewSecure5678!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 204


def test_password_change_wrong_old_password(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.post(
        "/api/v2/auth/password-change/",
        data={
            "oldPassword": "wrong",
            "newPassword1": "NewSecure5678!",
            "newPassword2": "NewSecure5678!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Validation failed"
    assert "oldPassword" in resp.json()["errors"]


def test_password_change_unauthenticated(client):
    resp = client.post(
        "/api/v2/auth/password-change/",
        data={
            "oldPassword": "x",
            "newPassword1": "y",
            "newPassword2": "y",
        },
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_password_change_mismatch(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.post(
        "/api/v2/auth/password-change/",
        data={
            "oldPassword": "correctpassword",
            "newPassword1": "NewSecure5678!",
            "newPassword2": "DifferentPassword!",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Validation failed"
    assert "newPassword2" in resp.json()["errors"]


# --- news/mark-visited ---


def test_news_mark_visited_authenticated(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.post(
        "/api/v2/spa/news/mark-visited/", content_type="application/json"
    )
    assert resp.status_code == 204


def test_news_mark_visited_anonymous(client):
    resp = client.post(
        "/api/v2/spa/news/mark-visited/", content_type="application/json"
    )
    assert resp.status_code == 204


# --- profile ---


def test_profile_get(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.get("/api/v2/profile/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert "firstName" in data
    assert "delayValue" in data
    assert "delayUnit" in data


def test_profile_get_unauthenticated(client):
    resp = client.get("/api/v2/profile/")
    assert resp.status_code == 401


def test_profile_put_success(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.put(
        "/api/v2/profile/",
        data={
            "firstName": "Alice",
            "lastName": "Smith",
            "email": "alice@example.com",
            "language": "en",
            "delayValue": 2,
            "delayUnit": "weeks",
        },
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["firstName"] == "Alice"
    user.refresh_from_db()
    assert user.notification_delay_days == 14


def test_profile_put_unauthenticated(client):
    resp = client.put(
        "/api/v2/profile/",
        data={
            "firstName": "X",
            "lastName": "",
            "email": "x@example.com",
            "language": "en",
            "delayValue": 1,
            "delayUnit": "days",
        },
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_profile_put_duplicate_email(client, auth_data):
    User = get_user_model()
    User.objects.create_user(
        username="other", password="pass", email="other@example.com"
    )
    user = auth_data["user"]
    client.force_login(user)
    resp = client.put(
        "/api/v2/profile/",
        data={
            "firstName": "Test",
            "lastName": "User",
            "email": "other@example.com",
            "language": "en",
            "delayValue": 1,
            "delayUnit": "days",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Validation failed"
    assert "email" in resp.json()["errors"]


def test_profile_put_invalid_delay_unit(client, auth_data):
    user = auth_data["user"]
    client.force_login(user)
    resp = client.put(
        "/api/v2/profile/",
        data={
            "firstName": "Test",
            "lastName": "User",
            "email": "testuser@example.com",
            "language": "en",
            "delayValue": 1,
            "delayUnit": "fortnights",
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Validation failed"
    assert "delayUnit" in resp.json()["errors"]


# --- account delete ---


def test_delete_account_success(client):
    User = get_user_model()
    user2 = User.objects.create_user(
        username="todelete", password="pass", email="del@example.com"
    )
    client.force_login(user2)
    resp = client.delete("/api/v2/account/")
    assert resp.status_code == 204
    assert not User.objects.filter(username="todelete").exists()


# ---------------------------------------------------------------------------
# POST /api/v2/observations/mark-as-seen/ (bulk mark)
# ---------------------------------------------------------------------------


def test_mark_all_as_seen_anonymous_returns_401(client, observations_data):
    """Anonymous users may not bulk-mark observations."""
    resp = client.post("/api/v2/observations/mark-as-seen/")
    assert resp.status_code == 401


def test_mark_all_as_seen_authenticated_returns_queued(
    client, observations_data, monkeypatch
):
    """An authenticated POST enqueues the job and returns queued=true."""
    from dashboard.views import jobs

    calls = []

    def fake_delay(queryset, user):
        calls.append({"count": queryset.count(), "user_id": user.pk})

    monkeypatch.setattr(jobs.mark_many_observations_as_seen, "delay", fake_delay)

    user = observations_data["user"]
    client.force_login(user)
    resp = client.post("/api/v2/observations/mark-as-seen/")

    assert resp.status_code == 200
    assert resp.json() == {"queued": True}
    assert len(calls) == 1
    assert calls[0]["count"] == 2  # both observations in the fixture
    assert calls[0]["user_id"] == user.pk


def test_mark_all_as_seen_respects_species_filter(
    client, observations_data, monkeypatch
):
    """A species filter narrows the queryset that gets handed to the job."""
    from dashboard.views import jobs

    captured: dict = {}

    def fake_delay(queryset, user):
        captured["ids"] = sorted(queryset.values_list("pk", flat=True))

    monkeypatch.setattr(jobs.mark_many_observations_as_seen, "delay", fake_delay)

    user = observations_data["user"]
    species = observations_data["species"]
    target_obs = observations_data["obs"]
    other_obs = observations_data["obs_other_species"]

    client.force_login(user)
    resp = client.post(f"/api/v2/observations/mark-as-seen/?speciesIds={species.pk}")

    assert resp.status_code == 200
    assert captured["ids"] == [target_obs.pk]
    assert other_obs.pk not in captured["ids"]


# ---------------------------------------------------------------------------
# Shared error schemas (PR1)
# ---------------------------------------------------------------------------


def test_detail_error_out_schema_shape():
    """DetailErrorOut wraps a single human-readable string."""
    from dashboard.api_v2_schemas import DetailErrorOut

    obj = DetailErrorOut(detail="Something went wrong")
    assert obj.detail == "Something went wrong"


def test_validation_error_out_schema_shape():
    """ValidationErrorOut carries a top-level detail and a per-field errors map."""
    from dashboard.api_v2_schemas import ValidationErrorOut

    obj = ValidationErrorOut(
        detail="Validation failed",
        errors={"speciesIds": ["At least one species must be selected"]},
    )
    assert obj.detail == "Validation failed"
    assert obj.errors == {"speciesIds": ["At least one species must be selected"]}


# ---------------------------------------------------------------------------
# SPA-only namespace (PR3)
# ---------------------------------------------------------------------------


def test_api_v2_spa_instance_exists_and_is_marked_internal():
    """The SPA helper API is a separate NinjaAPI marked as non-public."""
    from ninja import NinjaAPI

    from dashboard.api_v2 import api_v2, api_v2_spa

    assert isinstance(api_v2_spa, NinjaAPI)
    # Distinct namespace so django-ninja does not raise at startup.
    assert api_v2_spa.urls_namespace == "api-v2-spa"
    assert api_v2.urls_namespace != api_v2_spa.urls_namespace
    # Description warns consumers it is not part of the public contract.
    assert "not part of the public API contract" in api_v2_spa.description


def test_spa_openapi_schema_is_served_and_marked_internal(client):
    """The SPA helper API serves its own OpenAPI schema at /api/v2/spa/."""
    resp = client.get("/api/v2/spa/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "not part of the public API contract" in schema["info"]["description"]


def test_page_fragment_returns_html_under_spa_namespace(client):
    """page-fragments is served under /api/v2/spa/ and returns rendered HTML."""
    # Set all three language fields so the result is locale-independent
    # (get_content_in falls back to other languages when a field is empty).
    PageFragment.objects.create(
        identifier="welcome_text",
        content_en="# Hello",
        content_nl="# Hello",
        content_fr="# Hello",
    )
    resp = client.get("/api/v2/spa/page-fragments/welcome_text/")
    assert resp.status_code == 200
    assert "Hello" in resp.json()["html"]


def test_page_fragment_missing_returns_empty_html_under_spa_namespace(client):
    """A missing fragment yields {"html": ""} rather than a 404."""
    resp = client.get("/api/v2/spa/page-fragments/does_not_exist/")
    assert resp.status_code == 200
    assert resp.json()["html"] == ""


def test_relocated_endpoints_gone_from_public_namespace(client, alert_data):
    """The four in-scope endpoints (3 relocated, 1 deleted) no longer answer under /api/v2/.

    suggest-name returns 422 (not 404) because Ninja matches the path against
    the existing /alerts/{alert_id}/ route with "suggest-name" as a non-integer
    param - this is expected Ninja validation behaviour, not a successful response.
    """
    alert = alert_data["alert"]
    client.login(username="alertuser", password="12345")

    # suggest-name is gone; Ninja returns 422 (param type mismatch on {alert_id})
    # rather than 404 because /alerts/{alert_id}/ still exists. Assert a 4xx
    # client error (not == 422) so the test survives a future route change, while
    # still failing on a 2xx (endpoint accidentally re-added) or a 5xx server error.
    suggest_status = client.get("/api/v2/alerts/suggest-name/").status_code
    assert 400 <= suggest_status < 500, (
        f"suggest-name should return a client error on the public namespace "
        f"(got {suggest_status})"
    )

    # as-filters was deleted (dead code), so it is gone from the public surface too.
    assert client.get(f"/api/v2/alerts/{alert.pk}/as-filters/").status_code == 404
    assert (
        client.post(
            "/api/v2/news/mark-visited/", content_type="application/json"
        ).status_code
        == 404
    )
    assert client.get("/api/v2/page-fragments/welcome_text/").status_code == 404


def test_public_schema_excludes_relocated_endpoints(client):
    """The public /api/v2/ OpenAPI paths no longer mention the in-scope endpoints.

    django-ninja renders the full mount prefix into the path keys, so they look
    like /api/v2/alerts/. The anchor assertion below guards against a future
    ninja change to that format silently making the exclusion checks vacuous.
    """
    resp = client.get("/api/v2/openapi.json")
    assert resp.status_code == 200
    public_paths = set(resp.json()["paths"].keys())

    # Anchor: a known public endpoint must be present in the expected key format.
    assert "/api/v2/alerts/" in public_paths

    assert "/api/v2/alerts/suggest-name/" not in public_paths
    assert (
        "/api/v2/alerts/{alert_id}/as-filters/" not in public_paths
    )  # deleted entirely
    assert "/api/v2/news/mark-visited/" not in public_paths
    assert "/api/v2/page-fragments/{identifier}/" not in public_paths


def test_spa_schema_includes_relocated_endpoints(client):
    """The SPA schema is where the three relocated endpoints now live.

    django-ninja renders the full mount prefix into the SPA schema's path keys,
    so each path starts with /api/v2/spa/.
    """
    resp = client.get("/api/v2/spa/openapi.json")
    assert resp.status_code == 200
    spa_paths = set(resp.json()["paths"].keys())

    assert "/api/v2/spa/alerts/suggest-name/" in spa_paths
    assert "/api/v2/spa/news/mark-visited/" in spa_paths
    assert "/api/v2/spa/page-fragments/{identifier}/" in spa_paths
    # as-filters was deleted, not relocated - it must NOT reappear here.
    assert "/api/v2/spa/alerts/{alert_id}/as-filters/" not in spa_paths


# ---------------------------------------------------------------------------
# Typed response schemas (PR2)
# ---------------------------------------------------------------------------


def test_simple_dict_out_schemas_shapes():
    """The small status/value schemas carry exactly one typed field each."""
    from dashboard.api_v2_schemas import (
        AlertNameSuggestionOut,
        OkOut,
        PageFragmentOut,
        QueuedOut,
    )

    assert QueuedOut(queued=True).queued is True
    assert OkOut(ok=True).ok is True
    assert PageFragmentOut(html="<p>hi</p>").html == "<p>hi</p>"
    assert AlertNameSuggestionOut(name="My alert #1").name == "My alert #1"


def test_geojson_feature_collection_schema_shape():
    """The FeatureCollection schema nests features and preserves the crs member."""
    from dashboard.api_v2_schemas import (
        GeoJSONFeatureCollectionOut,
        GeoJSONFeatureOut,
    )

    fc = GeoJSONFeatureCollectionOut(
        type="FeatureCollection",
        crs={"type": "name", "properties": {"name": "EPSG:4326"}},
        features=[
            GeoJSONFeatureOut(
                type="Feature",
                id=1,
                properties={"pk": "1"},
                geometry={
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]],
                },
            )
        ],
    )
    assert fc.type == "FeatureCollection"
    assert fc.features[0].geometry["type"] == "Polygon"
    # crs must survive a round-trip dump (it is easy to accidentally drop).
    assert "crs" in fc.model_dump()


def test_area_geojson_response_is_unchanged_after_typing(client, area_endpoints_data):
    """Typing the response with a Schema must not drop keys (crs, feature id).

    The endpoint output must remain byte-identical to Django's raw geojson
    serializer output.
    """
    from django.core.serializers import serialize

    area = area_endpoints_data["area"]
    client.login(username="owner", password="pass")

    resp = client.get(f"/api/v2/areas/{area.pk}/geojson/")
    assert resp.status_code == 200

    expected = json.loads(serialize("geojson", [area], srid=4326))
    assert resp.json() == expected
    # Guard the specific members a naive schema would have dropped.
    assert "crs" in resp.json()
    assert "id" in resp.json()["features"][0]
