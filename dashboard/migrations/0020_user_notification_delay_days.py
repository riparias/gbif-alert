# Generated by Django 4.2.13 on 2024-10-10 12:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0019_migrate_obs_views"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="notification_delay_days",
            field=models.IntegerField(default=365),
        ),
    ]
