"""Helpers to map legacy GBIF backbone taxon keys to COL XR taxon keys, and to
check that a stored COL XR key still exists.

Isolated from the management command so the HTTP call is easy to mock in tests.
"""
import dataclasses

import requests
from django.conf import settings

COL_XR_CHECKLIST_KEY = settings.GBIF_COL_XR_CHECKLIST_KEY
_GBIF_MATCH_URL = "https://api.gbif.org/v2/species/match"
_TIMEOUT = 30


@dataclasses.dataclass
class ColMatchResult:
    col_key: str | None
    matched: bool
    detail: str  # human-readable match type / reason, for the report


def match_col_key(gbif_taxon_key: int) -> ColMatchResult:
    """Look up the COL XR key for a legacy integer backbone key.

    Uses the v2 match API's scientificNameID lookup, which already resolves a
    synonym input to its accepted COL usage. A result is accepted only when the
    match is EXACT and the usage is ACCEPTED; anything else is reported as
    unresolved for manual curation (never silently guessed).
    """
    resp = requests.get(
        _GBIF_MATCH_URL,
        params={
            "checklistKey": COL_XR_CHECKLIST_KEY,
            "scientificNameID": f"gbif:{gbif_taxon_key}",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    usage = data.get("usage") or {}
    diagnostics = data.get("diagnostics") or {}
    match_type = diagnostics.get("matchType", "NONE")
    status = usage.get("status")
    key = usage.get("key")

    if match_type == "EXACT" and status == "ACCEPTED" and key:
        return ColMatchResult(col_key=key, matched=True, detail=f"EXACT/{status}")

    if match_type == "EXACT" and status == "ACCEPTED" and not key:
        # Same matchType/status as an accepted match, but no usage key: make the
        # detail unambiguous so it can't be mistaken for a match in a report.
        detail = f"{match_type}/{status}/no-usage-key"
    else:
        detail = f"{match_type}/{status or 'no-usage'}"
    return ColMatchResult(col_key=None, matched=False, detail=detail)


def col_key_status(col_key: str) -> str | None:
    """Return the taxonomic status of a COL XR key, or None if it is retired.

    COL XR keys are not stable: Catalogue of Life ties a key to a name, so a
    change to the name retires the key (see #523). GBIF answers a retired or
    unknown key with HTTP 200 and matchType NONE rather than an error, and a
    download silently returns nothing for it - hence this explicit check.

    Returns the usage status as GBIF reports it ("ACCEPTED", "SYNONYM"...).
    Raises requests.RequestException on a network or HTTP error: "could not
    check" must never be mistaken for "retired".
    """
    resp = requests.get(
        _GBIF_MATCH_URL,
        params={"checklistKey": COL_XR_CHECKLIST_KEY, "usageKey": col_key},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    usage = data.get("usage") or {}
    match_type = (data.get("diagnostics") or {}).get("matchType", "NONE")
    if match_type == "NONE" or not usage:
        return None
    # A usage with no status would be a GBIF anomaly; report it as such rather
    # than as a retired key.
    return usage.get("status") or "UNKNOWN"
