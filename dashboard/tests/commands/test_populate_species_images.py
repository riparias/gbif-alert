import pytest
from io import StringIO
from unittest import mock
from django.core.management import call_command
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
        call_command("populate_species_images", "--dry-run", stdout=StringIO())
    sp.refresh_from_db()
    assert sp.image_url == ""
