# Generated by Django 3.2.9 on 2021-11-18 13:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_rename_gbif_id_dataset_gbif_dataset_key'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='occurrence',
            unique_together={('stable_id', 'data_import'), ('gbif_id', 'data_import')},
        ),
    ]