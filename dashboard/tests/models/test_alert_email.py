"""Notification email path: unseen_observations_sample and send_notification_email.

Written as a safety net before touching that code - it had no coverage.
"""

import datetime
import smtplib
from unittest import mock

import pytest
from django.conf import settings
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
    SentNotification,
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
    """A failed SMTP send returns False and leaves no trace of a send: the
    alert is not marked as sent (so the next run retries it) and no
    SentNotification is logged (so the D4.3 count only includes emails that
    actually went out)."""
    email_data["make_unseen"](1)
    alert = email_data["alert"]
    with mock.patch("dashboard.models.send_mail", side_effect=smtplib.SMTPException):
        assert alert.send_notification_email() is False
    alert.refresh_from_db()
    assert alert.last_email_sent_on is None
    assert len(mail.outbox) == 0
    assert not SentNotification.objects.exists()


def test_send_notification_email_records_the_send(email_data):
    """A successful send appends one SentNotification linking the alert and
    its user, with the unseen count the email reported. This row is the only
    record of the send once last_email_sent_on is overwritten by the next one,
    and it is what notification_stats counts."""
    email_data["make_unseen"](3)
    alert = email_data["alert"]

    assert alert.send_notification_email() is True

    sent = SentNotification.objects.get()
    assert sent.alert == alert
    assert sent.user == email_data["user"]
    assert sent.observations_count == 3
    assert sent.sent_at is not None


def test_sent_notification_survives_alert_deletion(email_data):
    """Deleting an alert keeps its sends in the log: the alert link is nulled
    but the user stays. Users clean up their alerts; without this the totals
    would shrink, and storing the user apart from the alert is what keeps
    those sends in the per-user breakdown."""
    email_data["make_unseen"](1)
    email_data["alert"].send_notification_email()

    email_data["alert"].delete()

    sent = SentNotification.objects.get()
    assert sent.alert is None
    assert sent.user == email_data["user"]  # still in the per-user breakdown


def test_sent_notification_survives_account_deletion_anonymised(email_data):
    """Deleting an account (which cascades to its alerts) keeps the row as an
    anonymous count: both links are nulled, so the instance totals hold while
    nothing ties the send back to the deleted person."""
    email_data["make_unseen"](1)
    email_data["alert"].send_notification_email()

    email_data["user"].delete()

    sent = SentNotification.objects.get()
    assert sent.alert is None
    assert sent.user is None


def test_send_notification_email_declares_the_user_language(email_data):
    email_data["make_unseen"](1)
    user = email_data["user"]
    user.language = "fr"
    user.save()

    assert email_data["alert"].send_notification_email() is True

    html = mail.outbox[0].alternatives[0][0]
    assert '<html lang="fr">' in html


def test_send_notification_email_uses_the_user_language_vernacular_name(email_data):
    """The species in the email shows its vernacular name in the recipient's
    language. The vernacular name is a modeltranslation field resolved against
    the active language, and the notification job runs as a management command
    where that is settings.LANGUAGE_CODE (English). Only the template's
    `{% language %}` block switches it: dropping that block would silently send
    English names to everyone."""
    species = Species.objects.get(name="Procambarus fallax")
    species.vernacular_name_en = "Slough crayfish"  # type: ignore[attr-defined]
    species.vernacular_name_fr = "Ecrevisse des marais"  # type: ignore[attr-defined]
    species.save()
    email_data["make_unseen"](1)
    user = email_data["user"]
    user.language = "fr"
    user.save()

    assert email_data["alert"].send_notification_email() is True

    html = mail.outbox[0].alternatives[0][0]
    assert "Ecrevisse des marais" in html
    assert "Slough crayfish" not in html


def test_send_notification_email_without_translation_is_sent_in_english(email_data):
    """A user whose language has no translation of the email still gets it, in
    English. A language can be added to the site before every text is
    translated; that must not stop its users' alert emails (with one template
    file per language, a missing file made every send fail)."""
    email_data["make_unseen"](1)
    user = email_data["user"]
    user.language = "de"  # no catalog and no template for German
    user.save()

    assert email_data["alert"].send_notification_email() is True

    html = mail.outbox[0].alternatives[0][0]
    assert "new observation(s) for this alert" in html


def test_send_notification_email_body_is_translated(email_data):
    """The email body is in the recipient's language, links included. The
    texts are gettext strings, so this also catches a template text drifting
    from its catalog entry (which would send English to every French user) or
    a translation that mangles the link placeholders."""
    email_data["make_unseen"](1)
    user = email_data["user"]
    user.language = "fr"
    user.save()
    alert = email_data["alert"]

    assert alert.send_notification_email() is True

    html = mail.outbox[0].alternatives[0][0]
    assert "Extrait des observations non-vues" in html
    assert "Merci," in html
    alert_path = reverse("dashboard:pages:alert-details", kwargs={"alert_id": alert.pk})
    assert f'href="{settings.SITE_BASE_URL}{alert_path}">page de l\'alerte</a>' in html
