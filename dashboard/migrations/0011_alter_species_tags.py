# Generated by Django 4.1.7 on 2023-03-24 08:51

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):
    dependencies = [
        ("taggit", "0005_auto_20220424_2025"),
        ("dashboard", "0010_remove_species_group_species_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="species",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="A comma-separated list of tags.",
                through="taggit.TaggedItem",
                to="taggit.Tag",
                verbose_name="Tags",
            ),
        ),
    ]
