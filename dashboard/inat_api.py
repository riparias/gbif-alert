"""
iNaturalist API v1 client for GBIF Alert.

Provides two public functions used by the management commands:
- get_observations()      — paginated observation fetch for a taxon + place
- get_inat_taxon_id()     — resolve an iNat taxon ID from a GBIF taxon key + scientific name
"""

import logging
import time
from datetime import date, timedelta
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

INAT_API_BASE = "https://api.inaturalist.org/v1"
_PAGE_SIZE = 200
_MAX_OFFSET = 9800  # iNat refuses offsets beyond this value


def _parse_location_from_obs(obs: dict):
    """Return a PostGIS Point (SRID 4326) from an iNat observation dict, or None if obscured/missing."""
    from django.contrib.gis.geos import Point  # local import to avoid Django setup at module level

    if obs.get("obscured"):
        return None
    location_str = obs.get("location")
    if not location_str:
        return None
    try:
        lat_str, lon_str = location_str.split(",")
        return Point(float(lon_str), float(lat_str), srid=4326)
    except (ValueError, AttributeError):
        return None


class InatApiError(Exception):
    pass


def _get(url: str, params: dict, requests_per_minute: int) -> dict:
    """Make a single GET request with rate limiting and basic retry on 429."""
    min_interval = 60.0 / requests_per_minute

    for attempt in range(3):
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 429:
            raw_retry = response.headers.get("Retry-After", "60")
            try:
                retry_after = int(raw_retry)
            except ValueError:
                retry_after = 60
            logger.warning("iNat rate limit hit, sleeping %ds", retry_after)
            time.sleep(retry_after)
            continue

        if not response.ok:
            raise InatApiError(
                f"iNat API returned {response.status_code} for {url}: {response.text[:200]}"
            )

        time.sleep(min_interval)
        return response.json()

    raise InatApiError(f"iNat API failed after retries for {url}")


def _date_range_chunks(
    start: date, end: date, chunk_days: int = 30
) -> Iterator[tuple[date, date]]:
    """Yield (chunk_start, chunk_end) pairs covering [start, end] inclusive."""
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def get_observations(
    taxon_id: int,
    place_id: int,
    quality_grades: list[str],
    requests_per_minute: int = 60,
    updated_since: str | None = None,
) -> Iterator[dict]:
    """
    Yield all iNaturalist observation dicts for the given taxon and place.

    Handles the 10,000-result offset cap by chunking over monthly date ranges.
    Each yielded dict is a raw iNat API observation object.

    :param taxon_id: iNaturalist taxon ID
    :param place_id: iNaturalist place ID (geographic scope)
    :param quality_grades: list of quality grades, e.g. ["research"] or ["research", "needs_id"]
    :param requests_per_minute: max requests per minute (default 60, iNat recommendation)
    :param updated_since: ISO 8601 datetime string; if set, only fetch obs updated after this time
    """
    base_params: dict = {
        "taxon_id": taxon_id,
        "place_id": place_id,
        "quality_grade": ",".join(quality_grades),
        "per_page": _PAGE_SIZE,
        "order": "asc",
        "order_by": "id",
    }
    if updated_since:
        base_params["updated_since"] = updated_since

    # For incremental imports (updated_since set), we don't need date chunking
    # since the result set is small. Use simple pagination.
    if updated_since:
        yield from _paginate(base_params, requests_per_minute)
        return

    # For full imports, chunk by month to stay under the 10k offset cap.
    # iNat data goes back to ~2008; we cover from 2000 to today.
    chunk_start = date(2000, 1, 1)
    chunk_end = date.today()

    for d1, d2 in _date_range_chunks(chunk_start, chunk_end, chunk_days=30):
        params = dict(base_params)
        params["d1"] = d1.isoformat()
        params["d2"] = d2.isoformat()
        yield from _paginate(params, requests_per_minute)


def _paginate(params: dict, requests_per_minute: int) -> Iterator[dict]:
    """Paginate through a single parameter set, stopping at the 10k offset cap."""
    page = 1
    total_fetched = 0

    while True:
        params["page"] = page
        data = _get(f"{INAT_API_BASE}/observations", params, requests_per_minute)

        results = data.get("results", [])
        if not results:
            break

        yield from results
        total_fetched += len(results)

        if total_fetched >= data.get("total_results", 0):
            break

        next_offset = page * _PAGE_SIZE
        if next_offset >= _MAX_OFFSET:
            logger.warning(
                "iNat offset cap (%d) reached for params %s — switch to smaller date chunks",
                _MAX_OFFSET,
                {k: v for k, v in params.items() if k != "page"},
            )
            break

        page += 1


def get_inat_taxon_id(gbif_taxon_key: int, scientific_name: str, requests_per_minute: int = 60) -> int | None:
    """
    Find the iNaturalist taxon ID corresponding to a GBIF taxon key.

    Strategy:
    1. Search iNat taxa by scientific name.
    2. Return the first result whose gbif_id matches the given gbif_taxon_key.
    3. If no match via gbif_id, fall back to an exact name match.

    :returns: iNat taxon ID integer, or None if not found.
    """
    params = {
        "q": scientific_name,
        "per_page": 10,
        "order_by": "observations_count",
    }

    try:
        data = _get(f"{INAT_API_BASE}/taxa", params, requests_per_minute)
    except InatApiError:
        logger.exception("iNat taxa lookup failed for '%s'", scientific_name)
        return None

    results = data.get("results", [])

    # Priority 1: exact gbif_id match (cast to int; iNat sometimes returns strings)
    for taxon in results:
        raw_gbif_id = taxon.get("gbif_id")
        try:
            inat_gbif_id: int | None = int(raw_gbif_id) if raw_gbif_id is not None else None
        except (ValueError, TypeError):
            inat_gbif_id = None
        if inat_gbif_id == gbif_taxon_key:
            logger.debug(
                "Matched '%s' to iNat taxon %d via gbif_id", scientific_name, taxon["id"]
            )
            return taxon["id"]

    # Priority 2: exact name match (case-insensitive)
    name_lower = scientific_name.lower()
    for taxon in results:
        if taxon.get("name", "").lower() == name_lower:
            logger.debug(
                "Matched '%s' to iNat taxon %d via name", scientific_name, taxon["id"]
            )
            return taxon["id"]

    logger.warning(
        "No iNat taxon found for '%s' (gbif_taxon_key=%d)", scientific_name, gbif_taxon_key
    )
    return None
