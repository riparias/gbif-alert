from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

from dashboard.models import Species

FETCH = "dashboard.management.commands.populate_vernacular_names.fetch_vernacular_names"

# Shaped like ChecklistBank's /dataset/{key}/taxon/{id}/vernacular response
# (trimmed to the keys the command reads), in the order ChecklistBank returns
# them: alphabetical by name.
HORNET_NAMES = [
    {"name": "Asian Hornet", "language": "eng"},
    {"name": "Asiatisk geithams", "language": "nor"},
    {"name": "Aziatische hoornaar", "language": "nld"},
    {"name": "Frelon asiatique", "language": "fra"},
    {"name": "Frelon a pattes jaunes", "language": "fra"},
    {"name": "Vespa asiatica", "language": "por"},
]


@pytest.fixture
def enabled(settings):
    """Set GBIF_ALERT["ENABLED_LANGUAGES"] for one test.

    GBIF_ALERT is a dict, so it is copied rather than mutated: pytest-django
    only restores attributes it replaced, not dicts changed in place.
    """

    def _set(*languages):
        settings.GBIF_ALERT = {**settings.GBIF_ALERT, "ENABLED_LANGUAGES": languages}

    return _set


def _hornet(**names):
    return Species.objects.create(
        name="Vespa velutina", gbif_col_taxon_key="7G3C6", **names
    )


def _run(*args):
    out, err = StringIO(), StringIO()
    call_command("populate_vernacular_names", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


@pytest.mark.django_db
def test_fills_blank_names_for_enabled_languages_only(enabled):
    """Blank names are filled, but only in the instance's enabled languages.

    Dutch is in the source but not enabled: writing it anyway would fill
    columns nobody sees, and silently pre-empt a curator's choice the day the
    language gets enabled.
    """
    enabled("en", "fr")
    sp = _hornet()
    with mock.patch(FETCH, return_value=HORNET_NAMES):
        _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_en == "Asian Hornet"
    assert sp.vernacular_name_fr == "Frelon asiatique"
    # modeltranslation makes the non-default language columns nullable.
    assert sp.vernacular_name_nl in (None, "")


@pytest.mark.django_db
def test_keeps_existing_names_by_default(enabled):
    """Without --overwrite an existing name is never replaced.

    There is no provenance field for names, so a non-blank name may have been
    typed by hand in the admin; the default run must be safe to repeat.
    """
    enabled("en", "fr")
    sp = _hornet(vernacular_name_fr="Frelon d'Asie")
    with mock.patch(FETCH, return_value=HORNET_NAMES):
        _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_fr == "Frelon d'Asie"
    assert sp.vernacular_name_en == "Asian Hornet"


@pytest.mark.django_db
def test_overwrite_replaces_existing_names(enabled):
    """--overwrite replaces names that are already set."""
    enabled("fr")
    sp = _hornet(vernacular_name_fr="Frelon d'Asie")
    with mock.patch(FETCH, return_value=HORNET_NAMES):
        _run("--overwrite")
    sp.refresh_from_db()
    assert sp.vernacular_name_fr == "Frelon asiatique"


@pytest.mark.django_db
def test_overwrite_never_blanks_a_name_missing_at_source(enabled):
    """--overwrite keeps a name the source has nothing to replace it with.

    Otherwise a gap in the source (or a source-side removal) would erase
    curated names.
    """
    enabled("fr")
    sp = _hornet(vernacular_name_fr="Frelon d'Asie")
    with mock.patch(FETCH, return_value=[{"name": "Asian Hornet", "language": "eng"}]):
        _run("--overwrite")
    sp.refresh_from_db()
    assert sp.vernacular_name_fr == "Frelon d'Asie"


@pytest.mark.django_db
def test_preferred_name_wins_over_first(enabled):
    """A name flagged preferred is chosen even if another one comes first."""
    enabled("fr")
    sp = _hornet()
    names = [
        {"name": "Frelon asiatique", "language": "fra"},
        {"name": "Frelon a pattes jaunes", "language": "fra", "preferred": True},
    ]
    with mock.patch(FETCH, return_value=names):
        _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_fr == "Frelon a pattes jaunes"


@pytest.mark.django_db
def test_norwegian_bokmal_matches_generic_norwegian(enabled):
    """`nb` is filled from names tagged `nor`, as COL tags most Norwegian names.

    Matching only `nob` would leave Norwegian blank for almost every species.
    """
    enabled("nb")
    sp = _hornet()
    with mock.patch(FETCH, return_value=HORNET_NAMES):
        _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_nb == "Asiatisk geithams"


@pytest.mark.django_db
def test_overlong_name_is_skipped_for_the_next_one(enabled):
    """A name longer than the 100-char column is skipped, not truncated.

    Saving it would raise on PostgreSQL and lose every language of the
    species; truncating would store a wrong name.
    """
    enabled("fr")
    sp = _hornet()
    names = [
        {"name": "A" * 101, "language": "fra"},
        {"name": "Frelon asiatique", "language": "fra"},
    ]
    with mock.patch(FETCH, return_value=names):
        _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_fr == "Frelon asiatique"


@pytest.mark.django_db
def test_dry_run_writes_nothing(enabled):
    """--dry-run reports what it would do but leaves the database untouched."""
    enabled("fr")
    sp = _hornet()
    with mock.patch(FETCH, return_value=HORNET_NAMES):
        out, _ = _run("--dry-run")
    sp.refresh_from_db()
    assert sp.vernacular_name_fr in (None, "")
    assert "Frelon asiatique" in out


@pytest.mark.django_db
def test_species_without_col_key_is_not_fetched(enabled):
    """A species with only a legacy key is skipped: names are looked up by COL key.

    Calling the API with a missing key would request a bogus URL.
    """
    enabled("fr")
    Species.objects.create(name="Legacius onlyus", gbif_taxon_key=999040)
    with mock.patch(FETCH, return_value=HORNET_NAMES) as fetch:
        _run()
    fetch.assert_not_called()


@pytest.mark.django_db
def test_one_failing_species_does_not_abort_the_run(enabled):
    """An error on one species is reported and the next species is still processed."""
    enabled("fr")
    Species.objects.create(name="Aaa failus", gbif_col_taxon_key="FAIL1")
    sp = _hornet()

    def fake_fetch(col_key):
        if col_key == "FAIL1":
            raise ValueError("boom")
        return HORNET_NAMES

    with mock.patch(FETCH, side_effect=fake_fetch):
        _, err = _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_fr == "Frelon asiatique"
    assert "Aaa failus" in err


@pytest.mark.django_db
def test_enabled_language_without_code_mapping_is_skipped(enabled):
    """An enabled language the command has no ISO 639-3 code for is skipped.

    A future language added to LANGUAGES without updating the mapping must
    not crash the run for the languages that are mapped.
    """
    enabled("en", "xx")
    sp = _hornet()
    with mock.patch(FETCH, return_value=HORNET_NAMES):
        _, err = _run()
    sp.refresh_from_db()
    assert sp.vernacular_name_en == "Asian Hornet"
    assert "xx" in err
