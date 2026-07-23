# Generated manually on 2026-02-19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0026_observation_verified"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="verified_filter",
            field=models.CharField(
                choices=[
                    ("all", "All observations"),
                    ("verified", "Verified only"),
                    ("unverified", "Unverified only"),
                ],
                default="all",
                max_length=10,
            ),
        ),
    ]
