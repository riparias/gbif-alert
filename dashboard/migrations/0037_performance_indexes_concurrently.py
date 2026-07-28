# Adds two btree indexes that the hot read paths need:
#
# - dashboard_o_date_id_idx on (date, id): the observation list defaults to
#   ORDER BY date DESC, id DESC LIMIT 20, which without an index sorts the whole
#   filtered set on every landing-page load. It also serves the date range
#   filter (date__gte / date__lte) in ObservationManager.filtered_from_my_params.
# - dashboard_ou_user_obs_idx on (user, observation): the unique_together on
#   ObservationUnseen already indexes (observation_id, user_id), but the
#   unseen-status filter starts from "the rows belonging to this user" and needs
#   the opposite column order.
#
# Both are created with CREATE INDEX CONCURRENTLY (hence atomic = False, as in
# migration 0029): a plain CREATE INDEX holds a write lock on
# dashboard_observation for its whole duration, which is not acceptable on a
# large production instance.
#
# AddIndexConcurrently is used rather than a raw RunSQL because these are plain
# field indexes declared in Meta.indexes: the operation emits the same
# CREATE INDEX CONCURRENTLY *and* keeps the migration state in sync, so the
# autodetector does not keep proposing the index again. (0029 had to use RunSQL
# because a functional/expression index cannot be declared in Meta.indexes.)

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("dashboard", "0036_allow_null_gbif_taxon_key"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="observation",
            index=models.Index(fields=["date", "id"], name="dashboard_o_date_id_idx"),
        ),
        AddIndexConcurrently(
            model_name="observationunseen",
            index=models.Index(
                fields=["user", "observation"], name="dashboard_ou_user_obs_idx"
            ),
        ),
    ]
