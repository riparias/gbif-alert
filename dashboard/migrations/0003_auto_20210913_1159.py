# Generated by Django 3.2.6 on 2021-09-13 11:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_populate_initial_species'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='species',
            options={'verbose_name_plural': 'species'},
        ),
        migrations.AddField(
            model_name='dataimport',
            name='imported_occurrences_counter',
            field=models.IntegerField(default=0),
        ),
    ]