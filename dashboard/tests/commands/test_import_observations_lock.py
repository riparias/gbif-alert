"""import_observations holds an advisory lock for its whole run (#258).

Two imports at once would rewrite the same rows, and the first to finish would
lift maintenance mode under the other. Checking this takes a second database
session: a session can always re-take a lock it already holds.
"""

from unittest import mock

import pytest
import requests_mock as requests_mock_module
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connection, connections
from django.test import override_settings
from maintenance_mode.core import get_maintenance_mode  # type: ignore

from dashboard.maintenance import (
    disable_maintenance_for_import,
    enable_maintenance_for_import,
)
from dashboard.management.commands.import_observations import (
    IMPORT_LOCK_KEY,
    Command,
)

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.sequential]


def try_lock(session) -> bool:
    with session.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [IMPORT_LOCK_KEY])
        return cursor.fetchone()[0]


@pytest.fixture
def other_session():
    """A second database session, standing in for another import process.

    Closing it releases whatever lock it took.
    """
    session = connections.create_connection("default")
    yield session
    session.close()


@pytest.fixture
def import_in_progress(other_session):
    """Another import is running: it holds the lock and set maintenance mode."""
    assert try_lock(other_session)
    enable_maintenance_for_import()
    yield
    disable_maintenance_for_import()


@override_settings(ADMINS=[("Admin", "admin@example.com")])
def test_second_run_is_refused_without_side_effects(
    import_in_progress, test_data, gbif_download_config, mailoutbox
):
    """While an import runs, a new run stops with an error and changes nothing.

    No GBIF download is requested (it would be wasted), and maintenance mode
    stays on: lifting it would expose the site while the running import rewrites
    the observations. The admins are emailed because an import still running
    when the next one starts means something is wrong. The Mocker has no routes,
    so a run that gets past the lock fails on its first GBIF request.
    """
    with requests_mock_module.Mocker() as m:
        with pytest.raises(CommandError, match="still in progress"):
            call_command("import_observations")

    assert m.call_count == 0
    assert get_maintenance_mode() is True
    assert len(mailoutbox) == 1
    assert "(import lock)" in mailoutbox[0].subject


def test_lock_lasts_for_the_whole_run_and_is_released_on_failure(other_session):
    """The lock is held while the import works, and a crash does not leave it
    behind.

    Taking the lock and dropping it right away would let overlapping runs
    through; keeping it after a failed import would refuse every later run in
    the same process.
    """
    lock_free_during_run = []

    def crashing_import(_options):
        lock_free_during_run.append(try_lock(other_session))
        raise RuntimeError("the import crashed")

    with mock.patch.object(Command, "_import", side_effect=crashing_import):
        with pytest.raises(RuntimeError):
            call_command("import_observations")

    assert lock_free_during_run == [False]
    assert try_lock(other_session) is True


def test_lost_connection_does_not_replace_the_import_error():
    """When the database connection dies during the run, the unlock fails too.

    That failure is harmless (Postgres released the lock with the connection),
    and it must not replace the import's own error: that error is what the
    admins need to read in the email (dropped connections happened, see #287).
    """
    broken_cursor = mock.patch.object(
        connections["default"],
        "cursor",
        side_effect=OperationalError("server closed the connection"),
    )

    def import_losing_the_connection(_options):
        broken_cursor.start()
        raise RuntimeError("the import crashed")

    try:
        with mock.patch.object(
            Command, "_import", side_effect=import_losing_the_connection
        ):
            with pytest.raises(RuntimeError):
                call_command("import_observations")
    finally:
        broken_cursor.stop()
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock_all()")
