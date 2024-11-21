# One-shot command to migrate the new unseen observations to the new mechanism
# (was hard to do in a data migration)

import datetime

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from dashboard.models import Observation, User, ObservationUnseen

one_year_ago = (timezone.now() - datetime.timedelta(days=365)).date()


class Command(BaseCommand):
    def handle(self, *args, **options):
        all_users = User.objects.all()

        for user in all_users:
            self.stdout.write(
                f"{str(datetime.datetime.now())} - Migrating data for user: "
                + user.username
            )

            # We only migrate that for unseen observations, pertaining to user alers and that are less than a year old
            for alert in user.alert_set.all():
                for obs in alert.observations():
                    if obs.date > one_year_ago:
                        if not obs.observationview_set.filter(user=user).exists():
                            try:
                                ObservationUnseen.objects.create(
                                    user=user, observation_id=obs.id
                                )
                            except IntegrityError:
                                # The same user might have already seen the observation from another alert
                                pass

        self.stdout.write("Done")
