"""Populate Species.gbif_col_taxon_key from the legacy integer gbif_taxon_key.

One-off, idempotent operator command. Calls the GBIF v2 match API per species.
EXACT + ACCEPTED matches are filled; everything else is left blank and reported
for manual curation (never silently guessed). Run after deploying the schema
migration and before resuming imports.
"""
import requests
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import Q

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

        # Only species that still need a key: reruns must not re-query GBIF for
        # already-resolved species (and doing so would widen the window for the
        # COL-key collision handled below).
        needs_col_key = Species.objects.filter(
            Q(gbif_col_taxon_key__isnull=True) | Q(gbif_col_taxon_key="")
        ).order_by("name")

        # A species with neither key cannot be converted - there is nothing to
        # match on. This should be unreachable via the API: Species.clean()
        # forbids having both keys blank, and the v2 API calls full_clean().
        # But the admin's bulk CSV/XLSX import (SpeciesResource in admin.py)
        # does not call full_clean(), so it - along with fixtures, data
        # migrations, and raw ORM writes - can still leave a species in this
        # state. Report it here rather than sending None to GBIF.
        no_taxon_key = list(needs_col_key.filter(gbif_taxon_key__isnull=True))
        unresolved_species = needs_col_key.exclude(gbif_taxon_key__isnull=True)

        for species in unresolved_species:
            try:
                result = match_col_key(species.gbif_taxon_key)
            except (requests.RequestException, ValueError) as exc:
                # A transient GBIF/network/parse error for one species must not
                # abort the whole run - record it and keep going.
                errors.append((species, str(exc)))
                continue

            if result.matched:
                if not dry_run:
                    species.gbif_col_taxon_key = result.col_key
                    try:
                        # Wrap in a savepoint so a unique-constraint collision
                        # rolls back only this save and leaves the surrounding
                        # transaction usable for the remaining species.
                        with transaction.atomic():
                            species.save(update_fields=["gbif_col_taxon_key"])
                    except IntegrityError:
                        # Two legacy taxa can resolve to the same accepted COL
                        # usage (synonyms are followed to their accepted key),
                        # which collides on the unique constraint. Report it for
                        # manual curation instead of aborting the run.
                        errors.append(
                            (
                                species,
                                f"COL key {result.col_key} is already assigned to "
                                "another species",
                            )
                        )
                        continue
                filled.append((species, result))
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
        self.stdout.write(
            f"NO TAXON KEY - needs manual curation ({len(no_taxon_key)}):"
        )
        for species in no_taxon_key:
            self.stdout.write(
                f"  {species.name} (no taxon key at all - enter one manually "
                "or the next import will be blocked)"
            )

        self.stdout.write("")
        self.stdout.write(f"ERRORS ({len(errors)}):")
        for species, message in errors:
            self.stdout.write(f"  {species.name} ({species.gbif_taxon_key}): {message}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write("(dry run - no changes written)")
