from django.db import migrations

from dashboard.models import AREA_PART_MAX_VERTICES

BACKFILL_SQL = f"""
    INSERT INTO dashboard_areapart (area_id, geom)
    SELECT id, ST_Subdivide(mpoly, {AREA_PART_MAX_VERTICES})
    FROM dashboard_area;
"""


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0040_areapart")]

    operations = [
        # Reverse is a no-op: migration 0040 drops the whole table when reversed.
        migrations.RunSQL(BACKFILL_SQL, migrations.RunSQL.noop),
    ]
