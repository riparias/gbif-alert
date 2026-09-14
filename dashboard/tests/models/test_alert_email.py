"""Notification email path: unseen_observations_sample and send_notification_email.

Written as a safety net before touching that code - it had no coverage.
"""

import datetime
import smtplib
from unittest import mock

import pytest
from django.contrib.gis.geos import Point
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from dashboard.models import (
    Alert,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    ObservationUnseen,
    Species,
    User,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def email_data():
    user = User.objects.create_user(
        username="mailuser", password="pass", email="mailuser@example.com"
    )
    species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)
    dataset = Dataset.objects.create(
        name="Test dataset", gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
    )
    basis_of_record = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    di = DataImport.objects.create(start=timezone.now())
    alert = Alert.objects.create(
        user=user,
        name="Crayfish watch",
        email_notifications_frequency=Alert.DAILY_EMAILS,
    )
    alert.species.add(species)

    def make_unseen(n: int) -> list[Observation]:
        """n observations, one per day ending today, all unseen by the user."""
        made = []
        for i in range(n):
            obs = Observation.objects.create(
                gbif_id=9000000 + i,
                occurrence_id=f"occ-{i}",
                species=species,
                date=datetime.date.today() - datetime.timedelta(days=n - 1 - i),
                data_import=di,
                initial_data_import=di,
                source_dataset=dataset,
                location=Point(5.09513, 50.48941, srid=4326),
                basis_of_record=basis_of_record,
            )
            ObservationUnseen.objects.create(observation=obs, user=user)
            made.append(obs)
        return made

    return {"user": user, "alert": alert, "make_unseen": make_unseen}


def test_unseen_observations_sample_caps_at_ten_most_recent_first(email_data):
    email_data["make_unseen"](12)
    sample = list(email_data["alert"].unseen_observations_sample())
    assert len(sample) == 10
    dates = [o.date for o in sample]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == datetime.date.today()


def test_unseen_observations_sample_below_cap_returns_all(email_data):
    email_data["make_unseen"](3)
    assert len(list(email_data["alert"].unseen_observations_sample())) == 3


def test_send_notification_email_sends_one_mail_with_count_and_marks_sent(email_data):
    made = email_data["make_unseen"](12)
    alert = email_data["alert"]
    assert alert.last_email_sent_on is None

    assert alert.send_notification_email() is True

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [email_data["user"].email]
    assert "12" in message.subject
    assert "Crayfish watch" in message.subject
    html = message.alternatives[0][0]
    assert "<b>12</b>" in html

    # The sample is in the body as detail links: the newest observation is
    # in, the oldest two are out (12 observations, sample of 10).
    def detail_url(obs):
        return reverse(
            "dashboard:pages:observation-details", kwargs={"stable_id": obs.stable_id}
        )

    assert detail_url(made[-1]) in html
    assert detail_url(made[0]) not in html
    assert detail_url(made[1]) not in html
    alert.refresh_from_db()
    assert alert.last_email_sent_on is not None


def test_send_notification_email_reports_smtp_failure(email_data):
    email_data["make_unseen"](1)
    alert = email_data["alert"]
    with mock.patch("dashboard.models.send_mail", side_effect=smtplib.SMTPException):
        assert alert.send_notification_email() is False
    alert.refresh_from_db()
    assert alert.last_email_sent_on is None
    assert len(mail.outbox) == 0
