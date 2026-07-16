"""Populate Species.gbif_col_taxon_key from the legacy integer gbif_taxon_key.

One-off, idempotent operator command. Calls the GBIF v2 match API per species.
EXACT + ACCEPTED matches are filled; everything else is left blank and reported
for manual curation (never silently guessed). Run after deploying the schema
migration and before resuming imports.
"""
import requests
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
        errors = []

        for species in Species.objects.all().order_by("name"):
            try:
                result = match_col_key(species.gbif_taxon_key)
            except (requests.RequestException, ValueError) as exc:
                # A transient GBIF/network/parse error for one species must not
                # abort the whole run - record it and keep going.
                errors.append((species, str(exc)))
                continue

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

        self.stdout.write("")
        self.stdout.write(f"ERRORS - could not query GBIF ({len(errors)}):")
        for species, message in errors:
            self.stdout.write(f"  {species.name} ({species.gbif_taxon_key}): {message}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write("(dry run - no changes written)")
