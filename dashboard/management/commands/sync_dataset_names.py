"""Name the datasets that the GBIF download left unnamed.

The import already does this at the end of every run. This command exists so an
instance can be fixed without waiting for (or forcing) a full re-import - for
example after a GBIF API outage, or after upgrading from a version that stored
the empty verbatim dwc:datasetName as the dataset name.
"""

from django.core.management.base import BaseCommand

from dashboard.management.commands.helpers import fill_missing_dataset_names
from dashboard.models import Dataset


class Command(BaseCommand):
    help = (
        "Fill in the name of every Dataset that has none, using the title held "
        "by the GBIF registry. Datasets that already have a name are untouched."
    )

    def handle(self, *args, **options) -> None:
        to_name = Dataset.objects.filter(name="").count()
        self.stdout.write(f"{to_name} dataset(s) without a name.")

        named = fill_missing_dataset_names(stdout=self.stdout)

        self.stdout.write(
            self.style.SUCCESS(f"Named {named} dataset(s) from the GBIF registry.")
        )
        if named < to_name:
            self.stdout.write(
                self.style.WARNING(
                    f"{to_name - named} dataset(s) still have no name: the GBIF "
                    "registry had no title for them, or was unreachable."
                )
            )
