# Generated manually on 2026-05-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0027_alert_verified_filter"),
    ]

    operations = [
        # Species: add iNaturalist taxon ID
        migrations.AddField(
            model_name="species",
            name="inat_taxon_id",
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
        # DataImport: add source field
        migrations.AddField(
            model_name="dataimport",
            name="source",
            field=models.CharField(
                choices=[("gbif", "GBIF"), ("inat", "iNaturalist")],
                default="gbif",
                max_length=10,
            ),
        ),
        # Observation: make gbif_id nullable (blank is sufficient; no DB null needed for CharField)
        migrations.AlterField(
            model_name="observation",
            name="gbif_id",
            field=models.CharField(blank=True, max_length=100),
        ),
        # Observation: add inat_id
        migrations.AddField(
            model_name="observation",
            name="inat_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        # Observation: add source field
        migrations.AddField(
            model_name="observation",
            name="source",
            field=models.CharField(
                choices=[("gbif", "GBIF"), ("inat", "iNaturalist")],
                default="gbif",
                max_length=10,
            ),
        ),
        # Observation: drop the old (gbif_id, data_import) unique_together
        migrations.AlterUniqueTogether(
            name="observation",
            unique_together={("stable_id", "data_import")},
        ),
        # Observation: add index on source
        migrations.AddIndex(
            model_name="observation",
            index=models.Index(
                fields=["source"], name="dashboard_o_source__idx"
            ),
        ),
    ]
