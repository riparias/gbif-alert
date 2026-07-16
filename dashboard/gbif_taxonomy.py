"""Helpers to map legacy GBIF backbone taxon keys to COL XR taxon keys.

Isolated from the management command so the HTTP call is easy to mock in tests.
"""
import dataclasses

import requests
from django.conf import settings

COL_XR_CHECKLIST_KEY = getattr(
    settings, "GBIF_COL_XR_CHECKLIST_KEY", "7ddf754f-d193-4cc9-b351-99906754a03b"
)
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
