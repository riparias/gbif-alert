"""Tests for the convert_taxon_keys_to_col operator command.

The command populates Species.gbif_col_taxon_key from the legacy integer
gbif_taxon_key via the GBIF v2 match API (mocked here). Taxon keys used below
are real: Branta canadensis -> 5WRC3, Polydrusus planifrons -> 4L6VJ.
"""
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
    """A cleanly-matched species gets its COL key written - the happy path the
    whole migration depends on."""
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    _run()
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "5WRC3"


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_leaves_blank_and_reports_unresolved(mock_match):
    """An unmatched species is left blank and named in the report.

    Why: the command never guesses. An unresolved species must reach a human,
    and leaving the key blank means the import guard will keep blocking until
    it is curated - failing loud rather than dropping the species silently.
    """
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
    """--dry-run previews the outcome without touching the database, so an
    operator can inspect the report before committing to the change."""
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    output = _run(dry_run=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key is None
    assert "dry run" in output.lower()


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_species_error_does_not_abort_run(mock_match):
    """One species failing to reach GBIF must not kill the whole run.

    Why: the command makes one HTTP call per species. Without per-species error
    handling a single transient network blip part-way through would abort the
    command and discard the report for every species already processed.
    """
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
    """Two legacy taxa resolving to the same COL key is reported, not a crash.

    Why: this is real, not hypothetical. COL XR lumps Polydrusus prasinus
    (legacy 1176451) into Polydrusus planifrons (legacy 7972617) - both resolve
    to the accepted usage 4L6VJ. Since gbif_col_taxon_key is unique, the second
    write raises IntegrityError; the command must absorb it, report the clash
    for curation, and carry on rather than abort half-done.
    """
    mock_match.return_value = ColMatchResult(
        col_key="4L6VJ", matched=True, detail="EXACT/ACCEPTED"
    )
    planifrons = Species.objects.create(
        name="Polydrusus planifrons", gbif_taxon_key=7972617
    )
    prasinus = Species.objects.create(
        name="Polydrusus prasinus", gbif_taxon_key=1176451
    )

    output = _run()  # must not raise despite the collision

    planifrons.refresh_from_db()
    prasinus.refresh_from_db()
    # Exactly one keeps the key; the other is reported rather than overwritten.
    assert {planifrons.gbif_col_taxon_key, prasinus.gbif_col_taxon_key} == {
        "4L6VJ",
        None,
    }
    assert "already assigned" in output.lower()
    assert "errors" in output.lower()


@patch("dashboard.management.commands.convert_taxon_keys_to_col.match_col_key")
def test_idempotent_rerun(mock_match):
    """Re-running is safe: already-resolved species keep their key.

    Why: operators re-run this after curating problem species, so a rerun must
    not raise on the unique constraint nor re-query GBIF for species that are
    already done (the command only looks at species still missing a key).
    """
    mock_match.return_value = ColMatchResult(
        col_key="5WRC3", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(name="Branta canadensis", gbif_taxon_key=5232437)
    _run()
    assert mock_match.call_count == 1

    _run()  # second run must not raise, and must skip the resolved species
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "5WRC3"
    assert mock_match.call_count == 1  # not re-queried
