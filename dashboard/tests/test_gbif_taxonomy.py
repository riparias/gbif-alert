"""Unit tests for the GBIF v2 match helper (legacy backbone key -> COL XR key).

The GBIF HTTP call is mocked; the response payloads below mirror real responses
observed from https://api.gbif.org/v2/species/match, and the taxon keys are the
real COL XR keys of the species named in each test.
"""
from unittest.mock import patch

from dashboard.gbif_taxonomy import match_col_key


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
