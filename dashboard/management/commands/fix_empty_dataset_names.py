# This script is necessary because of the following GBIF bug: https://github.com/gbif-alert/early-alert-webapp/issues/41
# A temporary workaround has been implemented in the import_observation command, but a script is necessary to fix
# preexisting entries in the datasets table.
#
# Hopefully this script can be removed once it has been run once in every environment, the workaround in
# import_observation can be removed after GBIF has fixed the initial bug and all downloads include correct dataset
# names.

from django.core.management import BaseCommand

from dashboard.models import Dataset
from .helpers import get_dataset_name_from_gbif_api


class Command(BaseCommand):
    def handle(self, *args, **options) -> None:
        self.stdout.write("Will fix every dataset with an empty name...")
        datasets = Dataset.objects.filter(name="")
        for dataset in datasets:
            self.stdout.write(f"dataset key={dataset.gbif_dataset_key}...")
            name = get_dataset_name_from_gbif_api(dataset.gbif_dataset_key)
            self.stdout.write(f"Found name: {name}")
            dataset.name = name
            dataset.save()
