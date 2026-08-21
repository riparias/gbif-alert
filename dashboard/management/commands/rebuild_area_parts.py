from django.core.management.base import BaseCommand

from dashboard.models import Area


class Command(BaseCommand):
    help = (
        "Rebuild the subdivided parts of areas. Area.save() does this "
        "automatically; this command covers areas created by paths that bypass "
        "it (bulk_create, queryset.update, loaddata, raw SQL) and lets an "
        "operator rebuild everything after a change to AREA_PART_MAX_VERTICES."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--area-id",
            type=int,
            default=None,
            help="Rebuild only this area. Default: every area.",
        )

    def handle(self, *args, **options):
        areas = Area.objects.all()
        if options["area_id"] is not None:
            areas = areas.filter(pk=options["area_id"])

        total = areas.count()
        for i, area in enumerate(areas, start=1):
            area.rebuild_parts()
            self.stdout.write(f"[{i}/{total}] rebuilt parts for {area}")

        self.stdout.write(self.style.SUCCESS(f"Rebuilt parts for {total} area(s)."))
