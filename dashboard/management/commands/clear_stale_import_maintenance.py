from django.core.management import BaseCommand

from dashboard.maintenance import clear_stale_import_maintenance


class Command(BaseCommand):
    help = (
        "Clear maintenance mode if it was left stranded ON by an interrupted import "
        "(e.g. a redeploy SIGKILLed the import). Leaves a manually enabled maintenance "
        "window untouched. Intended to run on web-container startup."
    )

    def handle(self, *args, **options) -> None:
        clear_stale_import_maintenance()
        self.stdout.write("Checked for stranded import maintenance mode.")
