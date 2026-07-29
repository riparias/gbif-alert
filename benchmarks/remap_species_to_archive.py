"""Relabel a throwaway database's species so a given archive actually imports.

Why this exists: the most realistic thing to benchmark an import against is a
clone of a real database - real observation volume, real users, real alerts,
real unseen records. But a real database's species carry the taxon keys of
whatever checklist it was last imported against, and an archive from a
different era carries different ones. With no overlap every row is skipped, the
import deletes every observation, and the run measures nothing.

Rather than fabricate a database, this relabels the clone's existing species
with the archive's taxon keys. Volume, users, alerts, unseen records and the
observation rows themselves are untouched, so the shape that drives import cost
is preserved; only which taxon a species claims to be changes. That is a lie
about the data and a fine approximation for timing.

Species beyond those already present are created if the archive needs more keys
than the database has species: a taxon key with no species aborts the whole
import, so every key the archive uses must be covered.

Refuses to run unless the resolved database name contains "bench".

    BENCH_DB_NAME=<clone> DJANGO_SETTINGS_MODULE=benchmarks.bench_settings \
      PYTHONPATH=. uv run python benchmarks/remap_species_to_archive.py <archive.zip>
"""

import collections
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "benchmarks.bench_settings")
django.setup()

from django.conf import settings  # noqa: E402
from dwca.read import DwCAReader  # type: ignore  # noqa: E402

from dashboard.management.commands.import_observations import _GBIF  # noqa: E402
from dashboard.models import Species  # noqa: E402

# Well clear of any real GBIF backbone key, so the synthetic species this may
# create cannot collide with a real one on the unique gbif_taxon_key column.
SYNTHETIC_TAXON_KEY_BASE = 900_000_000


def main(archive: str) -> int:
    name = settings.DATABASES["default"]["NAME"]
    if "bench" not in name:
        print(f"REFUSING: resolved database {name!r} does not contain 'bench'.")
        return 2
    print(f"target database: {name}")

    counter: collections.Counter = collections.Counter()
    with DwCAReader(archive, skip_metadata=True) as dwca:
        for (taxon_key,) in dwca.iter_terms([_GBIF + "taxonKey"]):
            key = taxon_key.strip()
            if key:
                counter[key] += 1

    # Most frequent first, so if anything ever does go uncovered it is the
    # rarest keys rather than the bulk of the archive.
    archive_keys = [key for key, _ in counter.most_common()]
    total_rows = sum(counter.values())
    print(
        f"archive uses {len(archive_keys)} distinct taxon keys over {total_rows} rows"
    )

    species = list(Species.objects.order_by("pk"))
    print(f"database has {len(species)} species")

    for existing, key in zip(species, archive_keys):
        existing.gbif_col_taxon_key = key
        existing.save(update_fields=["gbif_col_taxon_key"])

    # A row whose taxon key matches no species aborts the import outright, so
    # any surplus keys need a species of their own.
    surplus = archive_keys[len(species) :]
    for offset, key in enumerate(surplus):
        Species.objects.create(
            name=f"Bench filler species {key}",
            gbif_taxon_key=SYNTHETIC_TAXON_KEY_BASE + offset,
            gbif_col_taxon_key=key,
        )

    print(f"relabelled {min(len(species), len(archive_keys))} existing species")
    print(f"created {len(surplus)} filler species for the surplus keys")

    covered = {s.gbif_col_taxon_key for s in Species.objects.all()}
    missing = [k for k in archive_keys if k not in covered]
    rows_covered = sum(count for key, count in counter.items() if key in covered)
    print(f"coverage: {rows_covered}/{total_rows} rows, {len(missing)} keys uncovered")
    if missing:
        print("WARNING: uncovered keys will abort the import:", missing[:10])
        return 1

    blank = Species.objects.filter(gbif_col_taxon_key__isnull=True).count()
    blank += Species.objects.filter(gbif_col_taxon_key="").count()
    if blank:
        print(f"WARNING: {blank} species still have no taxon key; import will refuse")
        return 1

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
