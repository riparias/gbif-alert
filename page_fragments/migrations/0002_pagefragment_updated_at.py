# Generated by Django 4.1.7 on 2023-03-03 10:23

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("page_fragments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pagefragment",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
