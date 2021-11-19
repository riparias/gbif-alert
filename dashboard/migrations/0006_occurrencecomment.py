# Generated by Django 3.2.9 on 2021-11-18 14:13

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_alter_occurrence_unique_together'),
    ]

    operations = [
        migrations.CreateModel(
            name='OccurrenceComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('occurrence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.occurrence')),
            ],
        ),
    ]
