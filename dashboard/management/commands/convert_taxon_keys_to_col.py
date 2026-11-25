"""Populate Species.gbif_col_taxon_key from the legacy integer gbif_taxon_key.

One-off, idempotent operator command. Calls the GBIF v2 match API per species.
EXACT + ACCEPTED matches are filled; everything else is left blank and reported
for manual curation (never silently guessed). Run after deploying the schema
migration and before resuming imports.

With --recheck it also repairs keys that Catalogue of Life has retired since
(COL XR keys are not stable, see #523): each existing key is looked up at GBIF,
and a retired one is replaced by the key GBIF now gives for the legacy key. A
species without a legacy key gets the successor ChecklistBank recorded for its
retired key, provided GBIF knows that successor as an accepted taxon.
"""
import requests
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import Q

from dashboard.gbif_taxonomy import (
    ColMatchResult,
    col_key_status,
    col_key_successor,
    match_col_key,
)
from dashboard.models import Species


def successor_of_retired_key(retired_key: str) -> ColMatchResult:
    """Resolve a retired COL XR key through ChecklistBank's archive.

    For species with no legacy key to match on. The successor is only accepted
    when GBIF itself knows it as ACCEPTED: ChecklistBank can be a release ahead
    of GBIF, and its successor is not always the taxon GBIF would pick.
    """
    successor = col_key_successor(retired_key)
    if successor is None:
        return ColMatchResult(
            col_key=None, matched=False, detail="no successor at ChecklistBank"
        )
    status = col_key_status(successor)
    if status != "ACCEPTED":
        return ColMatchResult(
            col_key=None,
            matched=False,
            detail=f"ChecklistBank successor {successor} is "
            f"{status or 'unknown'} at GBIF",
        )
    return ColMatchResult(
        col_key=successor, matched=True, detail="ChecklistBank successor/ACCEPTED"
    )


class Command(BaseCommand):
    help = "Populate Species.gbif_col_taxon_key from the legacy GBIF backbone key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )
        parser.add_argument(
            "--recheck",
            action="store_true",
            help=(
                "Also look up every existing COL XR key at GBIF and replace the "
                "retired ones from the legacy key."
            ),
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
        to_resolve = list(needs_col_key.exclude(gbif_taxon_key__isnull=True))

        # --recheck: a species whose key was retired is resolved again, from
        # its legacy key like one that never had a key, or failing that from
        # ChecklistBank's archive. Its dead key is kept until a replacement is
        # found, and remembered for the report.
        retired_keys: dict[int, str] = {}
        retired_no_legacy_key = []
        not_accepted = []
        if options["recheck"]:
            for species in Species.objects.exclude(
                Q(gbif_col_taxon_key__isnull=True) | Q(gbif_col_taxon_key="")
            ).order_by("name"):
                try:
                    status = col_key_status(species.gbif_col_taxon_key)
                except (requests.RequestException, ValueError) as exc:
                    errors.append((species, str(exc)))
                    continue
                if status is None:
                    retired_keys[species.pk] = species.gbif_col_taxon_key
                    to_resolve.append(species)
                elif status != "ACCEPTED":
                    not_accepted.append((species, status))

        for species in to_resolve:
            try:
                if species.gbif_taxon_key is not None:
                    result = match_col_key(species.gbif_taxon_key)
                else:
                    # Only a rechecked species gets here: one with neither key
                    # is in no_taxon_key, not in to_resolve.
                    result = successor_of_retired_key(retired_keys[species.pk])
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
            elif species.gbif_taxon_key is None:
                retired_no_legacy_key.append((species, result))
            else:
                unresolved.append((species, result))

        self.stdout.write("")
        self.stdout.write(f"Filled ({len(filled)}):")
        for species, result in filled:
            replaced = (
                f" (replaces retired {retired_keys[species.pk]})"
                if species.pk in retired_keys
                else ""
            )
            self.stdout.write(
                f"  {species.name} ({species.gbif_taxon_key or 'no legacy key'}) "
                f"-> {result.col_key}{replaced} [{result.detail}]"
            )

        self.stdout.write("")
        self.stdout.write(f"UNRESOLVED - needs manual curation ({len(unresolved)}):")
        for species, result in unresolved:
            retired = (
                f" - COL key {retired_keys[species.pk]} is retired"
                if species.pk in retired_keys
                else ""
            )
            self.stdout.write(
                f"  {species.name} ({species.gbif_taxon_key}) "
                f"[{result.detail}]{retired}"
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

        if options["recheck"]:
            self.stdout.write("")
            self.stdout.write(
                "RETIRED KEY, no legacy key - needs manual curation "
                f"({len(retired_no_legacy_key)}):"
            )
            for species, result in retired_no_legacy_key:
                self.stdout.write(
                    f"  {species.name} ({species.gbif_col_taxon_key}) "
                    f"[{result.detail}] - search the name on gbif.org and enter "
                    "the new key manually"
                )

            self.stdout.write("")
            self.stdout.write(
                f"NOT ACCEPTED - key still exists, check manually ({len(not_accepted)}):"
            )
            for species, status in not_accepted:
                self.stdout.write(
                    f"  {species.name} ({species.gbif_col_taxon_key}) is {status}"
                )

        self.stdout.write("")
        self.stdout.write(f"ERRORS ({len(errors)}):")
        for species, message in errors:
            self.stdout.write(f"  {species.name} ({species.gbif_taxon_key}): {message}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write("(dry run - no changes written)")
