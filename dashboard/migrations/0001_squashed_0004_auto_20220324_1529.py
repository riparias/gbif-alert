# Generated by Django 3.2.12 on 2022-03-28 10:13

from django.conf import settings
import django.contrib.auth.models
import django.contrib.auth.validators
import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    replaces = [('dashboard', '0001_initial'), ('dashboard', '0002_alter_observation_species'), ('dashboard', '0003_alert_last_email_sent_on'), ('dashboard', '0004_auto_20220324_1529')]

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.Group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.Permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='DataImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('gbif_download_id', models.CharField(blank=True, max_length=255)),
                ('imported_observations_counter', models.IntegerField(default=0)),
                ('skipped_observations_counter', models.IntegerField(default=0)),
                ('gbif_predicate', models.JSONField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('gbif_dataset_key', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Observation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gbif_id', models.CharField(max_length=100)),
                ('occurrence_id', models.TextField()),
                ('stable_id', models.CharField(max_length=40)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=3857)),
                ('date', models.DateField()),
                ('individual_count', models.IntegerField(blank=True, null=True)),
                ('locality', models.TextField(blank=True)),
                ('municipality', models.TextField(blank=True)),
                ('basis_of_record', models.TextField(blank=True)),
                ('recorded_by', models.TextField(blank=True)),
                ('coordinate_uncertainty_in_meters', models.FloatField(blank=True, null=True)),
                ('data_import', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='dashboard.dataimport')),
                ('initial_data_import', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='occurrences_initially_imported', to='dashboard.dataimport')),
                ('source_dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.dataset')),
            ],
        ),
        migrations.CreateModel(
            name='Species',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('gbif_taxon_key', models.IntegerField(unique=True)),
                ('group', models.CharField(choices=[('PL', 'Plants'), ('CR', 'Crayfishes')], max_length=3)),
            ],
            options={
                'verbose_name_plural': 'species',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ObservationComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('observation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.observation')),
            ],
        ),
        migrations.AddField(
            model_name='observation',
            name='species',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='dashboard.species'),
        ),
        migrations.CreateModel(
            name='Area',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mpoly', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857)),
                ('name', models.CharField(max_length=255)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ObservationView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('observation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.observation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('observation', 'user')},
            },
        ),
        migrations.AlterUniqueTogether(
            name='observation',
            unique_together={('gbif_id', 'data_import'), ('stable_id', 'data_import')},
        ),
        migrations.AlterField(
            model_name='observation',
            name='species',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.species'),
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_notifications_frequency', models.CharField(choices=[('N', 'No emails'), ('D', 'Daily'), ('W', 'Weekly'), ('M', 'Monthly')], default='W', max_length=3)),
                ('areas', models.ManyToManyField(blank=True, help_text='Optional (no selection = notify me for all areas). To select multiple items, press and hold the Ctrl or Command key and click the items.', to='dashboard.Area')),
                ('datasets', models.ManyToManyField(blank=True, help_text='Optional (no selection = notify me for all datasets). To select multiple items, press and hold the Ctrl or Command key and click the items.', to='dashboard.Dataset')),
                ('species', models.ManyToManyField(blank=True, help_text='Optional (no selection = notify me for all species). To select multiple items, press and hold the Ctrl or Command key and click the items.', to='dashboard.Species')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('last_email_sent_on', models.DateTimeField(blank=True, default=None, null=True)),
            ],
        ),
    ]
