import pytest
from io import StringIO
from unittest import mock
from django.core.management import call_command
from django.core.management.base import CommandError
from dashboard.models import Species
from dashboard.species_images import ResolvedImage


def _wiki_result():
    return ResolvedImage(
        image_url="https://example.org/x.jpg",
        source_url="https://en.wikipedia.org/wiki/Testus",
        attribution="Jane Doe",
        license="CC BY-SA 4.0",
        source_type="wikipedia",
    )


@pytest.mark.django_db
def test_command_fills_empty_species():
    sp = Species.objects.create(name="Testus specius", gbif_taxon_key=999030)
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ):
        call_command("populate_species_images", stdout=StringIO())
    sp.refresh_from_db()
    assert sp.image_url == "https://example.org/x.jpg"
    assert sp.image_source_type == "wikipedia"


@pytest.mark.django_db
def test_command_never_overwrites_manual():
    sp = Species.objects.create(
        name="Testus specius", gbif_taxon_key=999031,
        image_url="https://manual.example/owned.jpg",
        image_source_type=Species.ImageSourceType.MANUAL,
    )
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ) as resolver:
        call_command("populate_species_images", "--refresh", stdout=StringIO())
    sp.refresh_from_db()
    assert sp.image_url == "https://manual.example/owned.jpg"
    resolver.assert_not_called()


@pytest.mark.django_db
def test_command_skips_already_filled_without_refresh():
    sp = Species.objects.create(
        name="Testus specius", gbif_taxon_key=999032,
        image_url="https://old.example/a.jpg",
        image_source_type=Species.ImageSourceType.WIKIPEDIA,
    )
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ) as resolver:
        call_command("populate_species_images", stdout=StringIO())
    resolver.assert_not_called()
    sp.refresh_from_db()
    assert sp.image_url == "https://old.example/a.jpg"


@pytest.mark.django_db
def test_command_dry_run_writes_nothing():
    sp = Species.objects.create(name="Testus specius", gbif_taxon_key=999033)
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ):
        out = StringIO()
        call_command("populate_species_images", "--dry-run", stdout=out)
    sp.refresh_from_db()
    assert sp.image_url == ""
    assert "1 species" in out.getvalue()


@pytest.mark.django_db
def test_limit_zero_processes_nothing():
    """--limit 0 must pass qs[:0] and call the resolver zero times."""
    Species.objects.create(name="Alphus betaus", gbif_taxon_key=999040)
    Species.objects.create(name="Gammus deltaus", gbif_taxon_key=999041)
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ) as resolver:
        call_command("populate_species_images", "--limit", "0", stdout=StringIO())
    resolver.assert_not_called()
    assert not Species.objects.filter(
        gbif_taxon_key__in=[999040, 999041]
    ).exclude(image_url="").exists()


@pytest.mark.django_db
def test_limit_one_processes_at_most_one():
    """--limit 1 fills exactly one of two empty species."""
    Species.objects.create(name="Alphus betaus", gbif_taxon_key=999042)
    Species.objects.create(name="Gammus deltaus", gbif_taxon_key=999043)
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ):
        call_command("populate_species_images", "--limit", "1", stdout=StringIO())
    filled = Species.objects.filter(
        gbif_taxon_key__in=[999042, 999043]
    ).exclude(image_url="").count()
    assert filled == 1


@pytest.mark.django_db
def test_species_flag_by_gbif_taxon_key_targets_correct_row():
    """--species <gbif_taxon_key> fills only that species."""
    sp_target = Species.objects.create(name="Alphus betaus", gbif_taxon_key=999044)
    sp_other = Species.objects.create(name="Gammus deltaus", gbif_taxon_key=999045)
    with mock.patch(
        "dashboard.management.commands.populate_species_images.resolve_species_image",
        return_value=_wiki_result(),
    ):
        call_command(
            "populate_species_images",
            "--species",
            str(sp_target.gbif_taxon_key),
            stdout=StringIO(),
        )
    sp_target.refresh_from_db()
    sp_other.refresh_from_db()
    assert sp_target.image_url == "https://example.org/x.jpg"
    assert sp_other.image_url == ""


@pytest.mark.django_db
def test_invalid_species_flag_raises_command_error():
    """Non-digit --species value must raise CommandError, not silently no-op."""
    with pytest.raises(CommandError):
        call_command(
            "populate_species_images",
            "--species",
            "not-a-number",
            stdout=StringIO(),
        )
