"""Unit tests for the GBIF v2 match helper (legacy backbone key -> COL XR key).

The GBIF HTTP call is mocked; the response payloads below mirror real responses
observed from https://api.gbif.org/v2/species/match, and the taxon keys are the
real COL XR keys of the species named in each test.
"""
from unittest.mock import patch

import pytest
import requests

from dashboard.gbif_taxonomy import col_key_status, match_col_key


def _fake_response(payload):
    class _R:
        def json(self):
            return payload

        def raise_for_status(self):
            return None

    return _R()


@patch("dashboard.gbif_taxonomy.requests.get")
def test_exact_accepted_match_returns_col_key(mock_get):
    """A clean match (EXACT + ACCEPTED) yields the COL key.

    This is the happy path the conversion command relies on: Branta canadensis
    (legacy backbone key 5232437) resolves to COL key 5WRC3.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": {
                "key": "5WRC3",
                "status": "ACCEPTED",
                "name": "Branta canadensis",
            },
            "diagnostics": {"matchType": "EXACT"},
        }
    )
    result = match_col_key(5232437)
    assert result.matched is True
    assert result.col_key == "5WRC3"


@patch("dashboard.gbif_taxonomy.requests.get")
def test_synonym_input_resolved_to_accepted_key(mock_get):
    """A legacy key that is now a synonym still yields the ACCEPTED COL key.

    Why: we look up by scientificNameID, and GBIF resolves a synonym input to
    its accepted usage server-side - so the helper needs no synonym-following of
    its own. Orconectes virilis (2227064) is accepted in COL as Faxonius virilis
    (7TVTY), and the response therefore already reports status ACCEPTED.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": {"key": "7TVTY", "status": "ACCEPTED", "name": "Faxonius virilis"},
            "diagnostics": {"matchType": "EXACT"},
        }
    )
    result = match_col_key(2227064)
    assert result.matched is True
    assert result.col_key == "7TVTY"


@patch("dashboard.gbif_taxonomy.requests.get")
def test_no_match_is_unresolved(mock_get):
    """An unknown legacy key is reported unresolved rather than guessed.

    GBIF answers matchType NONE with no usage at all; the reason is surfaced in
    `detail` so the operator can act on the conversion report.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": None,
            "diagnostics": {
                "matchType": "NONE",
                "issues": ["SCIENTIFIC_NAME_ID_NOT_FOUND"],
            },
        }
    )
    result = match_col_key(999999999)
    assert result.matched is False
    assert result.col_key is None
    assert "NONE" in result.detail


@patch("dashboard.gbif_taxonomy.requests.get")
def test_exact_accepted_but_missing_key_is_unresolved(mock_get):
    """EXACT + ACCEPTED but no usage key is still unresolved.

    Why: acceptance requires all three of matchType EXACT, status ACCEPTED, and
    a usage key. This covers the key-missing clause, and asserts the `detail`
    says so explicitly - otherwise a rejection would read identically to an
    accepted match ("EXACT/ACCEPTED") in the conversion report.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": {"status": "ACCEPTED"},
            "diagnostics": {"matchType": "EXACT"},
        }
    )
    result = match_col_key(123456)
    assert result.matched is False
    assert result.col_key is None
    assert "no-usage-key" in result.detail


@patch("dashboard.gbif_taxonomy.requests.get")
def test_non_accepted_or_fuzzy_is_unresolved(mock_get):
    """A non-ACCEPTED / non-EXACT match is never auto-accepted.

    Why: a fuzzy name match or a usage left at SYNONYM status is exactly the
    ambiguous case an operator must curate by hand - filling it in silently
    could point a species at the wrong taxon. Payload models a synonym usage
    (Polydrusus prasinus, S53PF) returned without resolution.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": {
                "key": "S53PF",
                "status": "SYNONYM",
                "name": "Polydrusus prasinus",
            },
            "diagnostics": {"matchType": "FUZZY"},
        }
    )
    result = match_col_key(1176451)
    assert result.matched is False
    assert result.col_key is None


@patch("dashboard.gbif_taxonomy.requests.get")
def test_col_key_status_of_live_key(mock_get):
    """A key that still exists reports its status, and is looked up by key.

    Aquarana catesbeiana (LN27W) is accepted. The request must use `usageKey`
    with the COL XR checklist: looking the key up any other way (as a name, or
    against the default backbone) would answer for a different taxon.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": {"key": "LN27W", "status": "ACCEPTED"},
            "diagnostics": {"matchType": "EXACT"},
        }
    )
    assert col_key_status("LN27W") == "ACCEPTED"
    params = mock_get.call_args.kwargs["params"]
    assert params["usageKey"] == "LN27W"
    assert params["checklistKey"]


@patch("dashboard.gbif_taxonomy.requests.get")
def test_col_key_status_of_retired_key_is_none(mock_get):
    """A retired key yields None - the case the import preflight blocks on.

    The payload is GBIF's real answer for C98, the key Lycaenidae had before
    COL added the authorship to the name (#523): HTTP 200, matchType NONE and
    no usage at all. Without this check the import would treat the taxon as
    having no occurrences.
    """
    mock_get.return_value = _fake_response(
        {
            "diagnostics": {
                "matchType": "NONE",
                "note": "All provided names were ignored since the usageKey was provided",
            },
            "synonym": False,
        }
    )
    assert col_key_status("C98") is None


@patch("dashboard.gbif_taxonomy.requests.get")
def test_col_key_status_of_synonym(mock_get):
    """A key that is alive but no longer accepted reports its real status.

    Why it matters: such a key still returns records, but only those identified
    under the synonym, so the caller must be able to tell it from an accepted
    one. Rana catesbeiana (6X35Q) is a synonym of Aquarana catesbeiana.
    """
    mock_get.return_value = _fake_response(
        {
            "usage": {"key": "6X35Q", "status": "SYNONYM"},
            "acceptedUsage": {"key": "LN27W"},
            "diagnostics": {"matchType": "EXACT"},
            "synonym": True,
        }
    )
    assert col_key_status("6X35Q") == "SYNONYM"


@patch("dashboard.gbif_taxonomy.requests.get")
def test_col_key_status_propagates_http_errors(mock_get):
    """A GBIF outage raises instead of answering None.

    Why: None means "retired" and blocks the import with a message telling the
    operator to change the key. An unreachable GBIF must not send them hunting
    for a replacement of a key that is perfectly valid.
    """
    mock_get.side_effect = requests.ConnectionError("GBIF unreachable")
    with pytest.raises(requests.ConnectionError):
        col_key_status("LN27W")
