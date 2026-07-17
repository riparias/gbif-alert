from io import StringIO
from unittest.mock import patch

import pytest
import requests
from django.core.management import call_command

from dashboard.gbif_taxonomy import ColMatchResult
from dashboard.models import Species

pytestmark = pytest.mark.django_db


def _run(**kwargs):
    out = StringIO()
    call_command("convert_taxon_keys_to_col", stdout=out, **kwargs)
    return out.getvalue()


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_fills_col_key_on_exact_match(mock_match):
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    _run()
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "5WRC3"


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_leaves_blank_and_reports_unresolved(mock_match):
    mock_match.return_value = ColMatchResult(
        col_key=None, matched=False, detail="NONE/no-usage"
    )
    sp = Species.objects.create(name="Ghostus specius", gbif_taxon_key=999999999)
    output = _run()
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key is None
    assert "Ghostus specius" in output
    assert "unresolved" in output.lower()


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_dry_run_writes_nothing(mock_match):
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    _run(dry_run=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key is None


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_species_error_does_not_abort_run(mock_match):
    ok_species = Species.objects.create(
        name="Branta canadensis", gbif_taxon_key=5232437
    )
    error_species = Species.objects.create(
        name="Ghostus specius", gbif_taxon_key=999999999
    )

    def side_effect(gbif_taxon_key):
        if gbif_taxon_key == error_species.gbif_taxon_key:
            raise requests.RequestException("GBIF is down")
        return ColMatchResult(col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED")

    mock_match.side_effect = side_effect

    output = _run()

    ok_species.refresh_from_db()
    error_species.refresh_from_db()
    assert ok_species.gbif_col_taxon_key == "5WRC3"
    assert error_species.gbif_col_taxon_key is None
    assert "Ghostus specius" in output
    assert "GBIF is down" in output
    assert "errors" in output.lower()


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_col_key_collision_is_reported_not_crashed(mock_match):
    # Two legacy taxa can resolve to the SAME accepted COL key (synonyms are
    # followed to their accepted usage). The unique constraint would collide;
    # the command must complete, fill one, and report the other as an error.
    mock_match.return_value = ColMatchResult(
        col_key="DUP1", matched=True, detail="EXACT/ACCEPTED"
    )
    first = Species.objects.create(name="Aaa first", gbif_taxon_key=111)
    second = Species.objects.create(name="Bbb second", gbif_taxon_key=222)

    output = _run()  # must not raise despite the collision

    first.refresh_from_db()
    second.refresh_from_db()
    assert {first.gbif_col_taxon_key, second.gbif_col_taxon_key} == {"DUP1", None}
    assert "already assigned" in output.lower()
    assert "errors" in output.lower()


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_idempotent_rerun(mock_match):
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    _run()
    _run()  # second run must not raise (unique constraint) and keeps the value
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "5WRC3"
