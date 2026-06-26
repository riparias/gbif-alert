"""Populate the optional Species.image_* fields from external sources.

Wikipedia/Wikimedia first, GBIF occurrence media as fallback. Never touches a
species whose image was set manually in the admin (image_source_type="manual").
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from dashboard.models import Species
from dashboard.species_images import resolve_species_image


class Command(BaseCommand):
    help = "Populate Species image fields from Wikipedia/GBIF."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Re-fetch auto-populated rows (never manual ones).",
        )
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--species",
            type=str,
            default=None,
            help="Restrict to one species by pk or gbif_taxon_key.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        refresh = options["refresh"]

        # Always exclude manually-curated images regardless of --refresh.
        qs = Species.objects.exclude(
            image_source_type=Species.ImageSourceType.MANUAL
        )
        if not refresh:
            qs = qs.filter(image_url="")

        if options["species"] is not None:
            value = options["species"]
            if not value.isdigit():
                raise CommandError(
                    f"--species value {value!r} must be a digit (pk or gbif_taxon_key)"
                )
            int_val = int(value)
            qs = qs.filter(Q(pk=int_val) | Q(gbif_taxon_key=int_val))

        qs = qs.order_by("name")
        if options["limit"] is not None:
            qs = qs[: options["limit"]]

        filled = 0
        for species in qs:
            resolved = resolve_species_image(species.name, species.gbif_taxon_key)
            if resolved is None:
                self.stdout.write(f"  no image: {species.name}")
                continue
            self.stdout.write(
                f"  {species.name} <- {resolved.source_type}: {resolved.image_url}"
            )
            filled += 1
            if dry_run:
                continue
            species.image_url = resolved.image_url
            species.image_source_url = resolved.source_url
            species.image_attribution = resolved.attribution
            species.image_license = resolved.license
            species.image_source_type = resolved.source_type
            species.save(
                update_fields=[
                    "image_url",
                    "image_source_url",
                    "image_attribution",
                    "image_license",
                    "image_source_type",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {filled} species updated"
                + (" (dry-run, nothing written)" if dry_run else "")
            )
        )
