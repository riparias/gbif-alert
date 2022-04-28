from django.core.management import BaseCommand

from django.utils import timezone
from maintenance_mode.core import get_maintenance_mode  # type: ignore

from dashboard.models import Alert


class Command(BaseCommand):
    def handle_alert(self, alert: Alert):
        self.stdout.write(f"Handling alert {alert.pk}")
        self.stdout.write(
            f"Alert details: frequency: {alert.get_email_notifications_frequency_display()} - "
            f"last sent on: {alert.last_email_sent_on}) - "
            f"{alert.unseen_observations().count()} unseen observations."
        )

        if alert.email_notifications_frequency == Alert.NO_EMAILS:
            self.stdout.write("User requested no emails, skipping")
        else:
            if alert.email_should_be_sent_now():
                self.stdout.write("We will send an email nor this alert")
                success = alert.send_notification_email()
                if success:
                    self.stdout.write("Mail successfully sent!")
                else:
                    self.stdout.write("Error sending the email, please check the logs")
            else:
                self.stdout.write(
                    "Sending an email is not deemed necessary now for this alert"
                )

    def handle(self, *args, **options) -> None:
        self.stdout.write(
            f"Will sent all necessary alert notifications. Current time is {timezone.now()}"
        )

        maintenance_mode = get_maintenance_mode()
        if not maintenance_mode:
            for alert in Alert.objects.all():
                try:  # In a try block so one alert failing will not prevent others from being sent
                    self.handle_alert(alert)
                except Exception as e:
                    self.stdout.write(f"Unexpected error handling alert: {e}")

            self.stdout.write("All done!")
        else:
            self.stdout.write("Error: Maintenance mode is set, skipping the operation!")
