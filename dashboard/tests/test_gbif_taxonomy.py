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
    # scientificNameID lookup already returns the ACCEPTED usage.
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
    mock_get.return_value = _fake_response(
        {
            "usage": {"key": "ABCDE", "status": "SYNONYM", "name": "Something"},
            "diagnostics": {"matchType": "FUZZY"},
        }
    )
    result = match_col_key(123)
    assert result.matched is False
