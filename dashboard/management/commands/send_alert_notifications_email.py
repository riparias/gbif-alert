from django.core.management import BaseCommand

from django.utils import timezone

from dashboard.models import Alert


class Command(BaseCommand):
    def handle_alert(self, alert: Alert):
        self.stdout.write(f"Handling alert f{alert.pk}")

        if alert.email_notifications_frequency == Alert.NO_EMAILS:
            self.stdout.write(f"User requested no emails, skipping")
        else:
            if alert.email_should_be_sent_now():
                self.stdout.write(
                    f"""An email should be sent now (frequency: {alert.get_email_notifications_frequency_display()} 
                    / last sent on: {alert.last_email_sent_on}) 
                    / {alert.unseen_observations().count()} unseen observations"""
                )
                alert.send_notification_email()

    def handle(self, *args, **options) -> None:
        self.stdout.write(
            f"Will sent all necessary alert notifications. Current time is {timezone.now}"
        )
        for alert in Alert.objects.all():
            try:  # In a try block so one alert failing will not prevent others from being sent
                self.handle_alert(alert)
            except Exception as e:
                self.stdout.write(f"Unexpected error handling alert: {e}")

        self.stdout.write("All done!")
