# Drops Django's default FK index on dashboard_observationunseen.user_id.
#
# Migration 0037 added dashboard_ou_user_obs_idx on (user_id, observation_id).
# A btree can be used for any prefix of its columns, so that index already
# serves everything the single-column (user_id) index served - including the
# cascade lookup when a User row is deleted - which leaves the FK index as pure
# write cost on a table the import rewrites in full on every run.
#
# The state change (db_index=False on the field) and the database change are
# separated so the DROP can run CONCURRENTLY: a plain DROP INDEX takes an
# ACCESS EXCLUSIVE lock on the table and would queue behind - and then block -
# live queries. Hence atomic = False, as in migrations 0029 and 0037.
#
# The index name is Django's deterministic FK index name (table + column +
# hash), so it is identical on every installation; IF EXISTS keeps the
# migration safe on a database where it has already been removed by hand.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

INDEX_NAME = "dashboard_observationunseen_user_id_c919a467"


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("dashboard", "0037_performance_indexes_concurrently"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="observationunseen",
                    name="user",
                    field=models.ForeignKey(
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME};",
                    reverse_sql=(
                        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
                        f"ON dashboard_observationunseen (user_id);"
                    ),
                ),
            ],
        ),
    ]
