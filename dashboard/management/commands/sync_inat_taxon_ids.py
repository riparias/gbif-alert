"""
Management command: sync_inat_taxon_ids

Populates Species.inat_taxon_id by querying the iNaturalist taxa API.
Safe to run multiple times (idempotent). Run once after adding new species,
or periodically to catch any taxonomy updates.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from dashboard.inat_api import get_inat_taxon_id
from dashboard.models import Species


class Command(BaseCommand):
    help = (
        "Sync iNaturalist taxon IDs for all species in the database. "
        "Run this once after adding new species before using import_inat_observations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-sync species that already have an inat_taxon_id set",
        )

    def handle(self, *args, **options):
        inat_config = settings.GBIF_ALERT.get("INAT_IMPORT_CONFIG", {})
        rpm = inat_config.get("REQUESTS_PER_MINUTE", 60)

        qs = Species.objects.all()
        if not options["force"]:
            qs = qs.filter(inat_taxon_id__isnull=True)

        total = qs.count()
        self.stdout.write(f"Syncing iNat taxon IDs for {total} species...")

        found = 0
        not_found = 0

        for species in qs:
            inat_id = get_inat_taxon_id(
                gbif_taxon_key=species.gbif_taxon_key,
                scientific_name=species.name,
                requests_per_minute=rpm,
            )

            if inat_id is not None:
                species.inat_taxon_id = inat_id
                species.save(update_fields=["inat_taxon_id"])
                self.stdout.write(
                    self.style.SUCCESS(f"  {species.name} → iNat taxon {inat_id}")
                )
                found += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f"  {species.name} → not found on iNaturalist")
                )
                not_found += 1

        self.stdout.write(
            f"\nDone. {found} matched, {not_found} not found on iNaturalist."
        )
        if not_found:
            self.stdout.write(
                "Species without an inat_taxon_id will be skipped during import_inat_observations."
            )
