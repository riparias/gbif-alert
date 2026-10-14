"""notification_stats: the D4.3 totals, from the SentNotification log."""

import datetime
import re
from io import StringIO

import pytest
from django.core.management import call_command

from dashboard.models import SentNotification, User

pytestmark = pytest.mark.django_db


def _sent(user: User | None, day: str) -> None:
    sent = SentNotification.objects.create(user=user, observations_count=1)
    # sent_at is auto_now_add, so it can only be backdated by an update. Noon
    # UTC keeps the month the same in any reasonable TIME_ZONE.
    SentNotification.objects.filter(pk=sent.pk).update(
        sent_at=datetime.datetime.fromisoformat(f"{day}T12:00:00+00:00")
    )


def _stats() -> str:
    out = StringIO()
    call_command("notification_stats", stdout=out)
    return out.getvalue()


def test_totals_per_month_and_per_user():
    """The three figures D4.3 needs, on sends spread over two months: the
    grand total with distinct recipients and the first send date (the log
    starts at deploy, so the report must say since when), then emails and
    distinct recipients per month, then emails per user. A deleted account
    counts as an email but not as a recipient, and is grouped on one line."""
    alice = User.objects.create_user(username="alice", email="alice@example.com")
    bob = User.objects.create_user(username="bob", email="bob@example.com")
    _sent(alice, "2026-09-15")
    _sent(alice, "2026-10-10")
    _sent(bob, "2026-10-12")
    _sent(None, "2026-10-14")  # a deleted account

    out = _stats()

    assert "4 notification emails sent to 2 users since 2026-09-15" in out
    assert re.search(r"2026-09\s+1\s+1\n", out)
    assert re.search(r"2026-10\s+3\s+2\n", out)
    assert re.search(r"alice\s+2\n", out)
    assert re.search(r"bob\s+1\n", out)
    assert re.search(r"\(deleted accounts\)\s+1\n", out)


def test_no_notification_yet():
    """On an instance that has sent nothing yet (e.g. right after deploying
    the log), the command says so instead of failing on the empty aggregate
    (the first send date is None)."""
    assert "No notification email recorded yet." in _stats()
