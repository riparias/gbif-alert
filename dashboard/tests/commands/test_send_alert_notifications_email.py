"""send_alert_notifications_email: sends for due alerts only.

Written as a safety net before touching the email path - it had no coverage.
"""

import datetime

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from dashboard.models import Alert
from dashboard.tests.models.test_alert_email import email_data  # noqa: F401

pytestmark = pytest.mark.django_db


def test_sends_for_a_due_alert_with_unseen_observations(email_data):  # noqa: F811
    email_data["make_unseen"](2)
    call_command("send_alert_notifications_email")
    assert len(mail.outbox) == 1
    email_data["alert"].refresh_from_db()
    assert email_data["alert"].last_email_sent_on is not None


def test_skips_alert_that_wants_no_emails(email_data):  # noqa: F811
    email_data["make_unseen"](2)
    alert = email_data["alert"]
    alert.email_notifications_frequency = Alert.NO_EMAILS
    alert.save()
    call_command("send_alert_notifications_email")
    assert len(mail.outbox) == 0


def test_skips_alert_emailed_too_recently(email_data):  # noqa: F811
    email_data["make_unseen"](2)
    alert = email_data["alert"]
    alert.last_email_sent_on = timezone.now() - datetime.timedelta(hours=1)
    alert.save()
    call_command("send_alert_notifications_email")  # daily, sent an hour ago
    assert len(mail.outbox) == 0


def test_skips_alert_with_nothing_unseen(email_data):  # noqa: F811
    call_command("send_alert_notifications_email")
    assert len(mail.outbox) == 0
