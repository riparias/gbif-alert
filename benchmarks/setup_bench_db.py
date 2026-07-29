"""Seed a benchmark database with species matching a DwCA's taxon keys.

The benchmark archive predates the COL migration, so its taxonKey values match
none of the real Species rows and every observation would be skipped - which
would measure an empty pipeline. This creates synthetic Species whose
gbif_col_taxon_key values are the archive's most frequent taxon keys, so nearly
every row is imported.

The species names are fictional. That is irrelevant to timing, and it is why
this must never be pointed at a real database.

Usage:
    DJANGO_SETTINGS_MODULE=benchmarks.bench_settings PYTHONPATH=. \\
      uv run python benchmarks/setup_bench_db.py <archive.zip> [top_n]
"""

import collections
import os
import sys

import django

# Default to the bench settings, but honour an explicit override so the guard
# below is what really protects the data, not this line.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "benchmarks.bench_settings")
django.setup()

from dwca.read import DwCAReader  # type: ignore  # noqa: E402

from dashboard.management.commands.import_observations import _GBIF  # noqa: E402
from dashboard.models import Species  # noqa: E402

DEFAULT_TOP_N = 200


def main(archive: str, top_n: int) -> int:
    db_name = django.db.connection.settings_dict["NAME"]
    if "bench" not in db_name:
        print(
            f"Refusing to seed database {db_name!r}: its name must contain "
            "'bench', to make it obvious this is a throwaway."
        )
        return 2

    counter: collections.Counter = collections.Counter()
    with DwCAReader(archive, skip_metadata=True) as dwca:
        for (taxon_key,) in dwca.iter_terms([_GBIF + "taxonKey"]):
            key = taxon_key.strip()
            if key:
                counter[key] += 1

    top = counter.most_common(top_n)
    covered = sum(count for _, count in top)
    total = sum(counter.values())
    print(f"{len(counter)} distinct taxon keys, top {top_n} cover {covered}/{total}")

    Species.objects.all().delete()
    Species.objects.bulk_create(
        [
            Species(
                name=f"Bench species {key}",
                gbif_taxon_key=index + 1,
                gbif_col_taxon_key=key,
            )
            for index, (key, _) in enumerate(top)
        ]
    )
    print(f"created {Species.objects.count()} species")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        raise SystemExit(2)
    n = int(sys.argv[2]) if len(sys.argv) == 3 else DEFAULT_TOP_N
    raise SystemExit(main(sys.argv[1], n))
