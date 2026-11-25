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
def test_species_with_no_keys_is_reported_as_needing_manual_curation(mock_match):
    """A species with neither key has nothing to convert FROM, and is flagged
    for manual curation rather than silently skipped.

    Why: Species.clean() forbids a species having both keys blank, and the v2
    API calls full_clean(), so this state should be unreachable through normal
    use. But the admin's bulk CSV/XLSX import does not call full_clean() (nor
    does plain ORM creation, as used here), so such a row can still land in
    the database - and it will block the next import_observations run. Sending
    it to match_col_key would call GBIF with None, so the command reports it
    instead, with wording that makes clear it needs action.
    """
    mock_match.return_value = ColMatchResult(
        col_key="4L6VJ", matched=True, detail="EXACT/ACCEPTED"
    )
    keyless = Species.objects.create(name="Newly described sp.")
    needs_conversion = Species.objects.create(
        name="Needs conversion sp.", gbif_taxon_key=5232437
    )

    output = _run()

    # The keyless species must never reach GBIF.
    mock_match.assert_called_once_with(needs_conversion.gbif_taxon_key)
    keyless.refresh_from_db()
    assert keyless.gbif_col_taxon_key is None  # left untouched
    assert "NO TAXON KEY - needs manual curation" in output
    assert "Newly described sp." in output
    assert "ERRORS (0)" in output


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


_CMD = "dashboard.management.commands.convert_taxon_keys_to_col"


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_recheck_replaces_a_retired_key(mock_match, mock_status):
    """--recheck swaps a retired COL key for the one GBIF now gives.

    Why: Catalogue of Life retires a key when the name behind it changes, and
    the import refuses to run on a retired key (#523). The case is real:
    Lycaenidae (legacy 5473) went from C98 to PR9JG when its authorship was
    added. The report names both keys so the operator can see what changed.
    """
    mock_status.return_value = None
    mock_match.return_value = ColMatchResult(
        col_key="PR9JG", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(
        name="Lycaenidae", gbif_taxon_key=5473, gbif_col_taxon_key="C98"
    )
    output = _run(recheck=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "PR9JG"
    assert "PR9JG (replaces retired C98)" in output


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_recheck_leaves_live_keys_alone(mock_match, mock_status):
    """A key that still exists is never re-derived from the legacy key.

    Why: an operator may have set a COL key by hand that differs from what the
    legacy key maps to. --recheck repairs dead keys only; it must not overwrite
    a deliberate, working choice.
    """
    mock_status.return_value = "ACCEPTED"
    sp = Species.objects.create(
        name="Branta canadensis", gbif_taxon_key=5232437, gbif_col_taxon_key="5WRC3"
    )
    _run(recheck=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "5WRC3"
    mock_match.assert_not_called()


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_recheck_keeps_retired_key_when_no_replacement(mock_match, mock_status):
    """A retired key with no clean replacement is kept and reported.

    Why: blanking it would lose the only trace of what was monitored, and
    guessing is ruled out. The dead key stays, so the import keeps refusing to
    run until a human decides.
    """
    mock_status.return_value = None
    mock_match.return_value = ColMatchResult(
        col_key=None, matched=False, detail="NONE/no-usage"
    )
    sp = Species.objects.create(
        name="Ghostus specius", gbif_taxon_key=999999999, gbif_col_taxon_key="DEAD1"
    )
    output = _run(recheck=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "DEAD1"
    assert "Ghostus specius" in output
    assert "COL key DEAD1 is retired" in output


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_recheck_reports_retired_key_without_legacy_key(mock_match, mock_status):
    """A COL-only species with a retired key is flagged for manual curation.

    Species described after the backbone froze have no legacy key, so there is
    nothing to re-derive from; the report must say so rather than skip them.
    """
    mock_status.return_value = None
    sp = Species.objects.create(name="Novum taxon", gbif_col_taxon_key="DEAD2")
    output = _run(recheck=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "DEAD2"
    assert "no legacy key" in output
    assert "Novum taxon (DEAD2)" in output
    mock_match.assert_not_called()


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_recheck_reports_non_accepted_key_without_changing_it(mock_match, mock_status):
    """A key that became a synonym is listed, not rewritten.

    Why: it still returns records, and which accepted taxon to monitor instead
    is a judgement call (the accepted name may cover more than the operator
    wants), so the command only points it out.
    """
    mock_status.return_value = "SYNONYM"
    sp = Species.objects.create(
        name="Rana catesbeiana", gbif_taxon_key=2427092, gbif_col_taxon_key="6X35Q"
    )
    output = _run(recheck=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "6X35Q"
    assert "Rana catesbeiana (6X35Q) is SYNONYM" in output
    mock_match.assert_not_called()


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_recheck_dry_run_writes_nothing(mock_match, mock_status):
    """--recheck --dry-run previews the replacement without applying it.

    A replaced key changes what the instance monitors, so the operator must be
    able to read the report before anything is written.
    """
    mock_status.return_value = None
    mock_match.return_value = ColMatchResult(
        col_key="PR9JG", matched=True, detail="EXACT/ACCEPTED"
    )
    sp = Species.objects.create(
        name="Lycaenidae", gbif_taxon_key=5473, gbif_col_taxon_key="C98"
    )
    output = _run(recheck=True, dry_run=True)
    sp.refresh_from_db()
    assert sp.gbif_col_taxon_key == "C98"
    assert "PR9JG (replaces retired C98)" in output


@patch(f"{_CMD}.col_key_status")
@patch(f"{_CMD}.match_col_key")
def test_without_recheck_existing_keys_are_not_looked_up(mock_match, mock_status):
    """The default run still only fills blank keys.

    Why: it is documented as idempotent and cheap to re-run; checking every
    existing key costs one GBIF request per species and is opt-in.
    """
    Species.objects.create(
        name="Lycaenidae", gbif_taxon_key=5473, gbif_col_taxon_key="C98"
    )
    _run()
    mock_status.assert_not_called()
    mock_match.assert_not_called()
