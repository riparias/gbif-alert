from io import StringIO
from unittest.mock import patch

import pytest
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
def test_idempotent_rerun(mock_match):
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    _run()
    _run()  # second run must not raise (unique constraint) and keeps the value
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "5WRC3"
