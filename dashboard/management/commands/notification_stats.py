from django.core.management import BaseCommand
from django.db.models import Count, Min
from django.db.models.functions import TruncMonth

from dashboard.models import SentNotification


class Command(BaseCommand):
    help = (
        "Print the notification emails sent by this instance: in total, per "
        "month and per user (from the SentNotification log)."
    )

    def handle(self, *args, **options) -> None:
        # Count("user", distinct=True) skips deleted accounts (user is null).
        per_group = {"emails": Count("pk"), "users": Count("user", distinct=True)}

        totals = SentNotification.objects.aggregate(**per_group, since=Min("sent_at"))
        if not totals["emails"]:
            self.stdout.write("No notification email recorded yet.")
            return
        self.stdout.write(
            f"{totals['emails']} notification emails sent to {totals['users']} "
            f"users since {totals['since']:%Y-%m-%d}"
        )

        self.stdout.write("\nPer month:\nmonth      emails  users")
        months = (
            SentNotification.objects.annotate(month=TruncMonth("sent_at"))
            .values("month")
            .annotate(**per_group)
            .order_by("month")
        )
        for row in months:
            self.stdout.write(
                f"{row['month']:%Y-%m}  {row['emails']:>8}  {row['users']:>5}"
            )

        self.stdout.write("\nPer user:")
        users = (
            SentNotification.objects.values("user__username")
            .annotate(emails=Count("pk"))
            .order_by("-emails", "user__username")
        )
        for row in users:
            name = row["user__username"] or "(deleted accounts)"
            self.stdout.write(f"{name:<30}  {row['emails']:>6}")
