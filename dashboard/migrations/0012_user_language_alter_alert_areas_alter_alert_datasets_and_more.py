# Generated by Django 4.2 on 2023-04-18 11:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0011_alter_species_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="language",
            field=models.CharField(
                choices=[("en", "English"), ("fr", "French"), ("nl", "Dutch")],
                default="en-us",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="alert",
            name="areas",
            field=models.ManyToManyField(
                blank=True,
                help_text="Optional (no selection = notify me for all areas). To select multiple items, press and hold the Ctrl or Command key and click the items.",
                to="dashboard.area",
                verbose_name="areas",
            ),
        ),
        migrations.AlterField(
            model_name="alert",
            name="datasets",
            field=models.ManyToManyField(
                blank=True,
                help_text="Optional (no selection = notify me for all datasets). To select multiple items, press and hold the Ctrl or Command key and click the items.",
                to="dashboard.dataset",
                verbose_name="datasets",
            ),
        ),
        migrations.AlterField(
            model_name="alert",
            name="email_notifications_frequency",
            field=models.CharField(
                choices=[
                    ("N", "No emails"),
                    ("D", "Daily"),
                    ("W", "Weekly"),
                    ("M", "Monthly"),
                ],
                default="W",
                max_length=3,
                verbose_name="email notifications frequency",
            ),
        ),
        migrations.AlterField(
            model_name="alert",
            name="name",
            field=models.CharField(max_length=255, verbose_name="name"),
        ),
        migrations.AlterField(
            model_name="alert",
            name="species",
            field=models.ManyToManyField(
                blank=True,
                help_text="Optional (no selection = notify me for all species). To select multiple items, press and hold the Ctrl or Command key and click the items.",
                to="dashboard.species",
                verbose_name="species",
            ),
        ),
    ]
