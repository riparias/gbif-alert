# Generated by Django 4.2 on 2023-06-06 08:09

from django.db import migrations


def make_alerts_explicit(apps, schema_editor):
    """Make sure alerts explictly list the targeted species"""
    Alert = apps.get_model("dashboard", "Alert")
    Species = apps.get_model("dashboard", "Species")
    for alert in Alert.objects.all():
        if alert.species.all().count() == 0:
            alert.species.add(*Species.objects.all())


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0014_alter_alert_areas_alter_alert_species"),
    ]

    operations = [migrations.RunPython(make_alerts_explicit)]