# Generated manually on 2026-02-19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0025_observation_identification_verification_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="observation",
            name="verified",
            field=models.BooleanField(default=False),
        ),
    ]
