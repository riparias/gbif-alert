# Adds a functional geography GiST index on dashboard_observation.location so that
# ST_DWithin(ST_Transform(location, 4326)::geography, ...) queries in the
# "approaching" and "both" area filter modes can use an index instead of a seq scan.
#
# Without this index, a 3 km approaching query on 1 M observations takes ~21 s.
# With it, the same query takes ~1.8 s (warm cache).
#
# The Geography() wrapper is equivalent to ::geography but is valid inside CREATE INDEX.
#
# CREATE INDEX CONCURRENTLY cannot run inside a transaction, so atomic = False.

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("dashboard", "0028_alert_area_filter"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX CONCURRENTLY dashboard_observation_location_geog_idx "
                "ON dashboard_observation "
                "USING GIST (Geography(ST_Transform(location, 4326)));"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS dashboard_observation_location_geog_idx;"
            ),
        ),
    ]
