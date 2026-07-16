"""Populate Species.gbif_col_taxon_key from the legacy integer gbif_taxon_key.

One-off, idempotent operator command. Calls the GBIF v2 match API per species.
EXACT + ACCEPTED matches are filled; everything else is left blank and reported
for manual curation (never silently guessed). Run after deploying the schema
migration and before resuming imports.
"""
from django.core.management.base import BaseCommand

from dashboard.gbif_taxonomy import match_col_key
from dashboard.models import Species


class Command(BaseCommand):
    help = "Populate Species.gbif_col_taxon_key from the legacy GBIF backbone key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        filled = []
        unresolved = []

        for species in Species.objects.all().order_by("name"):
            result = match_col_key(species.gbif_taxon_key)
            if result.matched:
                filled.append((species, result))
                if not dry_run:
                    species.gbif_col_taxon_key = result.col_key
                    species.save(update_fields=["gbif_col_taxon_key"])
            else:
                unresolved.append((species, result))

        self.stdout.write("")
        self.stdout.write(f"Filled ({len(filled)}):")
        for species, result in filled:
            self.stdout.write(
                f"  {species.name} ({species.gbif_taxon_key}) -> "
                f"{result.col_key} [{result.detail}]"
            )

        self.stdout.write("")
        self.stdout.write(f"UNRESOLVED - needs manual curation ({len(unresolved)}):")
        for species, result in unresolved:
            self.stdout.write(
                f"  {species.name} ({species.gbif_taxon_key}) [{result.detail}]"
            )

        if dry_run:
            self.stdout.write("")
            self.stdout.write("(dry run - no changes written)")
