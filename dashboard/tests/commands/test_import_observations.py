import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import requests_mock
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.db.models import QuerySet
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from maintenance_mode.core import set_maintenance_mode  # type: ignore

from dashboard.models import (
    Species,
    DataImport,
    Observation,
    Dataset,
    ObservationComment,
    User,
    Alert,
    ObservationUnseen,
)

THIS_SCRIPT_PATH = Path(__file__).parent
SAMPLE_DATA_PATH = THIS_SCRIPT_PATH / "sample_data"


def predicate_builder_belgium(species_list: QuerySet[Species]):
    """
    Build a GBIF.org download predicate for Belgian observations, after 2000.

    Species list is taken from the GBIF Alert database.
    """

    return {
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "COUNTRY", "value": "BE"},
                {
                    "type": "in",
                    "key": "TAXON_KEY",
                    "values": [f"{s.gbif_taxon_key}" for s in species_list],
                },
                {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "present"},
                {
                    "type": "greaterThanOrEquals",
                    "key": "YEAR",
                    "value": 2010,
                },
            ],
        }
    }


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
class ImportObservationsTest(TransactionTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="testuser",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
            notification_delay_days=365,
        )

        Species.objects.all().delete()  # There are initially a few species in the database (loaded in data migration)
        self.lixus = Species.objects.create(
            name="Lixus bardanae", gbif_taxon_key=1224034
        )
        self.polydrusus = Species.objects.create(
            name="Polydrusus planifrons", gbif_taxon_key=7972617
        )

        inaturalist = Dataset.objects.create(
            name="iNaturalist", gbif_dataset_key="50c9509d-22c7-4a22-a47d-8c48425ef4a7"
        )

        self.dataset_without_observations = Dataset.objects.create(
            name="Dataset without observations",
            gbif_dataset_key="50c9509d-22c7-4a22-a47d-8c48425ef4a8",
        )

        self.alert_referencing_unused_dataset = Alert.objects.create(
            name="Alert referencing unused dataset",
            user=self.user,
        )
        self.alert_referencing_unused_dataset.datasets.add(
            self.dataset_without_observations, inaturalist
        )
        self.alert_referencing_unused_dataset.species.add(self.lixus)

        # We need this one to make sure the observation is automatically marked as as seen
        # in test_observation_unseen_migrated()
        self_alert_referencing_obs_unseen_to_be_replaced = Alert.objects.create(
            name="Alert referencing observation unseen to be replaced",
            user=self.user,
        )
        self_alert_referencing_obs_unseen_to_be_replaced.species.add(self.polydrusus)

        # This observation will be replaced during the import process
        # because there's a row with the same occurrence_id and dataset_key in the DwC-A
        self.initial_di = DataImport.objects.create(start=timezone.now())
        self.observation_unseen_to_be_replaced = Observation.objects.create(
            gbif_id=1,
            occurrence_id="https://www.inaturalist.org/observations/33366292",
            source_dataset=inaturalist,
            species=self.polydrusus,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=self.initial_di,
            initial_data_import=self.initial_di,
            location=Point(5.09513, 50.48941, srid=4326),
        )

        self.observation_seen_to_be_replaced = Observation.objects.create(
            gbif_id=3,
            occurrence_id="https://www.inaturalist.org/observations/42577016",
            source_dataset=inaturalist,
            species=self.polydrusus,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=self.initial_di,
            initial_data_import=self.initial_di,
            location=Point(5.09513, 50.48941, srid=4326),
        )

        # This one has no equivalent in the DwC-A
        observation_not_replaced = Observation.objects.create(
            gbif_id=2,
            occurrence_id="2",
            source_dataset=inaturalist,
            species=self.lixus,
            date=datetime.date.today(),
            data_import=self.initial_di,
            initial_data_import=self.initial_di,
            location=Point(5.09513, 50.48941, srid=4326),
        )

        ObservationComment.objects.create(
            author=self.user,
            observation=self.observation_unseen_to_be_replaced,
            text="This is a comment to migrate",
        )

        self.observation_unseen_to_migrate = ObservationUnseen.objects.create(
            user=self.user, observation=self.observation_unseen_to_be_replaced
        )

        # We also create this one, so we can check it gets deleted in the new import
        # process, and that it doesn't prevent the related observation to be deleted
        self.observation_unseen_to_delete = ObservationUnseen.objects.create(
            user=self.user, observation=observation_not_replaced
        )

    def test_initial_data_import_value_replaced(self):
        """The initial_data_import field still points to the first import after an occurrence gets replaced"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observation_new_import = Observation.objects.get(
            occurrence_id="https://www.inaturalist.org/observations/33366292"
        )

        self.assertEqual(observation_new_import.initial_data_import, self.initial_di)
        # Just to be sure: the data_import field points to the new/current one
        latest_di = DataImport.objects.latest("id")
        self.assertEqual(observation_new_import.data_import, latest_di)

    def test_initial_data_import_value_new(self):
        """Make sure the initial_data_import field points to the current data import for a completely new occurrence"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations = Observation.objects.all().order_by("id")
        totally_new_obs = observations[0]
        latest_di = DataImport.objects.latest("id")
        self.assertEqual(totally_new_obs.initial_data_import, latest_di)
        self.assertEqual(totally_new_obs.data_import, latest_di)

    def test_transaction(self) -> None:
        """The whole process happens in a transaction: no DB changes are made if an exception occurs near the end
        of the process"""

        MODELS_TO_OBSERVE = [
            Dataset,
            Species,
            ObservationComment,
            DataImport,
            Observation,
        ]

        models_before = {}  # key: model name. value: list representation

        for Model in MODELS_TO_OBSERVE:
            models_before[Model._meta.label] = list(Model.objects.all().order_by("pk"))

        # DataImport.complete() is called at the end of the import process. We make it fail so we can check what happens
        with mock.patch(
            "dashboard.models.DataImport.complete", side_effect=Exception("Boom!")
        ):
            with open(
                SAMPLE_DATA_PATH / "gbif_download.zip", "rb"
            ) as gbif_download_file:
                with self.assertRaises(Exception):
                    call_command("import_observations", source_dwca=gbif_download_file)

        # We left the command due to an exception, so maintenance mode is still set
        # We disable it, so it doesn't break the rest of the test suite
        set_maintenance_mode(False)

        # Note: cannot use assertQuerySetEqual because of lazy evaluation
        for Model in MODELS_TO_OBSERVE:
            self.assertEqual(
                list(Model.objects.all().order_by("pk")),
                models_before[Model._meta.label],
            )

    def test_ignore_unusable_observations(self) -> None:
        """The DwC-A contains 13 records, but some are not usable:

        - missing coordinates: 3 records
        - no year: 1 record
        - no occurrence ID: 1 record
        - absence: 1 record

        => so, only 7 should be loaded after the import process
        """

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        self.assertEqual(Observation.objects.all().count(), 7)

        self.assertEqual(
            DataImport.objects.latest("id").skipped_observations_counter, 6
        )
        # TODO: more testing to make sure it's the usable ones that were loaded?

    def test_load_observations_values(self) -> None:
        """Imported values look correct"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations = Observation.objects.all().order_by("id")
        # We assume observations are loaded in the DwC-A rows order
        occ = observations[0]  #
        self.assertEqual(str(occ.date), "2024-10-10")
        self.assertEqual(occ.gbif_id, "3044795455")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/42671325",
        )
        self.assertEqual(occ.stable_id, "4aa3b8d81c4a62c89b73a4416af7d51968c29104")
        self.assertEqual(
            occ.species_id, self.polydrusus.pk
        )  # This also test the fallback to the acceptedTaxonKey (https://github.com/riparias/gbif-alert/issues/93)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 3.315567)  # type: ignore
        self.assertAlmostEqual(lat, 51.354473)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        # The dataset name has been updated (compared to test data) because it was updated from the name in the
        # DwC-A (https://github.com/riparias/gbif-alert/issues/257)
        self.assertEqual(
            occ.source_dataset.name, "iNaturalist research-grade observations"
        )

        occ = observations[1]
        self.assertEqual(str(occ.date), "2020-04-19")
        self.assertEqual(occ.gbif_id, "2609350465")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/42577016",
        )
        self.assertEqual(occ.stable_id, "6a6fc5bd50d1ead0f33f32c843b185bbfbd7c166")
        self.assertEqual(
            occ.species_id, self.polydrusus.pk
        )  # This also test the fallback to the speciesKey (https://github.com/riparias/gbif-alert/issues/93)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 3.254023)  # type: ignore
        self.assertAlmostEqual(lat, 50.664364)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name, "iNaturalist research-grade observations"
        )
        self.assertEqual(
            occ.references, "https://www.inaturalist.org/observations/42577016"
        )

        occ = observations[
            2
        ]  # Fourth row in CSV (third was skipped because of date issue)

        self.assertEqual(str(occ.date), "2018-05-05")
        self.assertEqual(occ.gbif_id, "2423231120")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/33366292",
        )
        self.assertEqual(occ.stable_id, "a4ec033c2da60ef1095c50f4445bf305904aa336")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 3.52526)  # type: ignore
        self.assertAlmostEqual(lat, 51.150846)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name, "iNaturalist research-grade observations"
        )

        occ = observations[3]

        self.assertEqual(str(occ.date), "2018-09-05")
        self.assertEqual(occ.gbif_id, "1914197587")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/16227955",
        )
        self.assertEqual(occ.stable_id, "48f6d956f104c4c83174e9ea7cbb0b545e995d4d")
        self.assertEqual(occ.species_id, self.lixus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 4.360086)  # type: ignore
        self.assertAlmostEqual(lat, 50.646894)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name, "iNaturalist research-grade observations"
        )
        self.assertEqual(occ.recorded_by, "Nicolas Noé")
        self.assertEqual(occ.basis_of_record, "HUMAN_OBSERVATION")
        self.assertEqual(occ.locality, "Lillois")
        self.assertEqual(occ.municipality, "Braine L'alleud")
        self.assertEqual(occ.individual_count, 1)
        self.assertEqual(occ.coordinate_uncertainty_in_meters, 23)

        occ = observations[4]

        self.assertEqual(str(occ.date), "2018-05-11")
        self.assertEqual(occ.gbif_id, "1847507314")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/12411012",
        )
        self.assertEqual(occ.stable_id, "baddab78a96bf75f3dd98b0be69b035364f6a77e")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 2.59858)  # type: ignore
        self.assertAlmostEqual(lat, 51.097573)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name, "iNaturalist research-grade observations"
        )

        occ = observations[5]

        self.assertEqual(str(occ.date), "2017-05-15")
        self.assertEqual(occ.gbif_id, "1802743867")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/9294095",
        )
        self.assertEqual(occ.stable_id, "85b4076d572cdc8782746d3dc0252fab7e2a5cd2")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 4.454613)  # type: ignore
        self.assertAlmostEqual(lat, 51.26503)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name, "iNaturalist research-grade observations"
        )

        occ = observations[6]

        self.assertEqual(str(occ.date), "1950-06-18")
        self.assertEqual(occ.gbif_id, "1315928743")
        self.assertEqual(
            occ.occurrence_id,
            "Ugent:UGMD:16879",
        )
        self.assertEqual(occ.stable_id, "cc478993ca998a9be116bad94e6b31ddf2128f33")
        self.assertEqual(occ.species_id, self.lixus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 4.418141)  # type: ignore
        self.assertAlmostEqual(lat, 51.27734)  # type: ignore
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name,
            "Ghent university - Zoology Museum - Insect Collection",
        )
        # We stop there, the remaining rows in DwC-A miss either the location or the occurrence id

    def test_observation_comments_migrated(self) -> None:
        comment = ObservationComment.objects.all()[0]  # there's only one...
        previous_observation_id = comment.observation_id
        previous_stable_id = comment.observation.stable_id

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        comment.refresh_from_db()
        self.assertNotEqual(comment.observation_id, previous_observation_id)
        self.assertEqual(comment.observation.stable_id, previous_stable_id)

    def test_observation_unseen_migrated(self) -> None:
        ou = self.observation_unseen_to_migrate
        previous_observation_id = ou.observation_id
        previous_stable_id = ou.observation.stable_id

        # We have to increase the user delay to make sure the observation is not marked as seen
        # because it's considered old
        self.user.notification_delay_days = 365 * 20
        self.user.save()

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        ou.refresh_from_db()
        self.assertNotEqual(ou.observation_id, previous_observation_id)
        self.assertEqual(ou.observation.stable_id, previous_stable_id)

    def test_unmigrated_ou_gets_deleted(self) -> None:
        ou_id = self.observation_unseen_to_delete.id

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(id=ou_id)

    def test_old_observations_deleted(self) -> None:
        """The old observations (replaced and not replaced) are deleted from the database after a new import"""
        id_observations_before = list(
            Observation.objects.all().values_list("id", flat=True)
        )
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        id_observations_after = list(
            Observation.objects.all().values_list("id", flat=True)
        )
        self.assertFalse(bool(set(id_observations_before) & set(id_observations_after)))

    def test_dataimport_object_created(self) -> None:
        count_before = DataImport.objects.count()
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        self.assertEqual(DataImport.objects.count(), count_before + 1)

    def test_dataimport_object_values(self):
        """Values of the DataImport object are created

        Side effect of the observations_counter check: we also check that newly created observations reference the
        correct DataImport object
        """
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        di = DataImport.objects.latest("id")
        self.assertIsNotNone(di.start)
        self.assertIsNotNone(di.end)
        self.assertGreater(di.end, di.start)
        self.assertTrue(di.completed)
        self.assertEqual(di.gbif_download_id, "0076720-210914110416597")
        self.assertIsNone(di.gbif_predicate)
        self.assertEqual(
            di.imported_observations_counter,
            Observation.objects.filter(data_import=di).count(),
        )

    def test_gbif_request_not_necessary(self) -> None:
        """No HTTP request emitted if the --source-dwca option is used"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            with requests_mock.Mocker() as m:
                call_command(
                    "import_observations",
                    source_dwca=gbif_download_file,
                )
                request_history = m.request_history
                self.assertEqual(len(request_history), 0)

    def test_seen_status_unseen_to_seen_age(self) -> None:
        """An old unseen observation is marked as seen after import (because it's older than the user delay)"""
        # user delay is the default (365 days)
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations_after = Observation.objects.all()
        obs = observations_after.get(
            occurrence_id=self.observation_unseen_to_be_replaced.occurrence_id
        )

        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(observation=obs, user=self.user)

    def test_seen_status_unseen_to_unseen(self) -> None:
        """Same situation than test_seen_status_unseen_to_seen_age() but we force the
        user delay to be very long, so the unseen status is kept"""
        self.user.notification_delay_days = 365 * 20
        self.user.save()

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations_after = Observation.objects.all()
        obs = observations_after.get(
            occurrence_id=self.observation_unseen_to_be_replaced.occurrence_id
        )

        ObservationUnseen.objects.get(observation=obs, user=self.user)

    def test_seen_status_seen_to_seen(self) -> None:
        """An observation that was already seen remains seen after import"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations_after = Observation.objects.all()

        # Case 1: An existing seen observation has been replaced, it should be marked as seen
        case1 = observations_after.get(
            occurrence_id=self.observation_seen_to_be_replaced.occurrence_id
        )
        # Case 1 result: unseen not found => seen
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(observation=case1, user=self.user)

    def test_seen_status_new_to_seen_because_no_alert(self) -> None:
        """New observation in the system. It's more recent than the user delay, but is
        not part of any alert, so it's marked as seen"""

        # Make sure we don't have any lingering alert
        Alert.objects.filter(user=self.user).delete()

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations_after = Observation.objects.all()
        last_di = DataImport.objects.latest("id")

        # Those are the observations that are totally new in the system
        fresh_observations = observations_after.filter(initial_data_import=last_di)

        recent_observation_not_in_alerts = fresh_observations.get(
            stable_id="4aa3b8d81c4a62c89b73a4416af7d51968c29104"
        )

        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(
                observation=recent_observation_not_in_alerts, user=self.user
            )

    def test_seen_status_new_to_seen_because_old(self) -> None:
        """New observation in the system. It's older than the user delay, so it's
        marked as seen (even if it's part of an alert)"""

        # We create an alert that matches the observation (all lixus bardanae observations)
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        alert.species.add(self.lixus)

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        observations_after = Observation.objects.all()
        last_di = DataImport.objects.latest("id")

        # Those are the observations that are totally new in the system
        fresh_observations = observations_after.filter(initial_data_import=last_di)

        old_lixus_bardanae = fresh_observations.get(occurrence_id="Ugent:UGMD:16879")

        # It is considered seen because it's older than the user delay
        with self.assertRaises(ObservationUnseen.DoesNotExist):
            ObservationUnseen.objects.get(
                observation=old_lixus_bardanae, user=self.user
            )

    def test_seen_status_new_to_unseen(self) -> None:
        """New observation in the system. It's more recent than the user delay, and is
        part of an alert, so it's marked as unseen"""

        # Test code: identical to test_seen_status_new_to_seen_because_old() but we
        # pretend we're running the import in 1950
        alert = Alert.objects.create(
            user=self.user, email_notifications_frequency=Alert.DAILY_EMAILS
        )
        alert.species.add(self.lixus)

        mocked = datetime.datetime(1950, 7, 1, tzinfo=ZoneInfo("UTC"))
        with mock.patch("django.utils.timezone.now", mock.Mock(return_value=mocked)):
            with open(
                SAMPLE_DATA_PATH / "gbif_download.zip", "rb"
            ) as gbif_download_file:
                call_command("import_observations", source_dwca=gbif_download_file)

        observations_after = Observation.objects.all()
        last_di = DataImport.objects.latest("id")

        # Those are the observations that are totally new in the system
        fresh_observations = observations_after.filter(initial_data_import=last_di)

        old_lixus_bardanae = fresh_observations.get(occurrence_id="Ugent:UGMD:16879")

        # It is considered not seen because it's only a few days old
        ObservationUnseen.objects.get(observation=old_lixus_bardanae, user=self.user)

    @override_settings(
        GBIF_ALERT={
            "GBIF_DOWNLOAD_CONFIG": {
                "PREDICATE_BUILDER": predicate_builder_belgium,
                "USERNAME": "riparias-dev",
                "PASSWORD": "riparias-dev",
            },
        }
    )
    def test_gbif_request(self) -> None:
        """The correct HTTP requests are emitted to gbif.org"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            with requests_mock.Mocker() as m:
                m.post(
                    "https://api.gbif.org/v1/occurrence/download/request", text="1000"
                )
                m.get(
                    "https://api.gbif.org/v1/occurrence/download/request/1000",
                    body=gbif_download_file,
                )

                call_command("import_observations")

                request_history = m.request_history

                # 1. A request for a new download wirth the correct filters was sent first
                self.assertEqual(request_history[0].method, "POST")
                self.assertEqual(
                    request_history[0].url,
                    "https://api.gbif.org/v1/occurrence/download/request",
                )
                self.assertEqual(
                    request_history[0].text,
                    '{"predicate": {"type": "and", "predicates": [{"type": "equals", "key": "COUNTRY", "value": "BE"}, {"type": "in", "key": "TAXON_KEY", "values": ["1224034", "7972617"]}, {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "present"}, {"type": "greaterThanOrEquals", "key": "YEAR", "value": 2010}]}}',
                )

                # 2. A request to download the DwCA file was subsequently emitted
                self.assertEqual(request_history[1].method, "GET")
                self.assertEqual(
                    request_history[1].url,
                    "https://api.gbif.org/v1/occurrence/download/request/1000",
                )

    @override_settings(
        GBIF_ALERT={
            "GBIF_DOWNLOAD_CONFIG": {
                "PREDICATE_BUILDER": predicate_builder_belgium,
                "USERNAME": "riparias-dev",
                "PASSWORD": "riparias-dev",
            },
        }
    )
    def test_gbif_predicate_stored(self):
        """In case of GBIF request, the predicate is stored in the DataImport object"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            with requests_mock.Mocker() as m:
                m.post(
                    "https://api.gbif.org/v1/occurrence/download/request", text="1000"
                )
                m.get(
                    "https://api.gbif.org/v1/occurrence/download/request/1000",
                    body=gbif_download_file,
                )

                call_command("import_observations")

                di = DataImport.objects.latest("id")
                self.assertDictEqual(
                    di.gbif_predicate,
                    {
                        "predicate": {
                            "type": "and",
                            "predicates": [
                                {"key": "COUNTRY", "type": "equals", "value": "BE"},
                                {
                                    "key": "TAXON_KEY",
                                    "type": "in",
                                    "values": ["1224034", "7972617"],
                                },
                                {
                                    "key": "OCCURRENCE_STATUS",
                                    "type": "equals",
                                    "value": "present",
                                },
                                {
                                    "key": "YEAR",
                                    "type": "greaterThanOrEquals",
                                    "value": 2010,
                                },
                            ],
                        }
                    },
                )

    def test_dataset_cleanup_mechanism(self):
        """At the end of the import process, datasets that have no longer any associated observations are deleted

        Alerts referencing those empty datasets are updated appropriately
        """
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_observations", source_dwca=gbif_download_file)

        self.alert_referencing_unused_dataset.refresh_from_db()

        with self.assertRaises(Dataset.DoesNotExist):
            self.dataset_without_observations.refresh_from_db()

        self.assertEqual(self.alert_referencing_unused_dataset.datasets.count(), 1)
        self.assertEqual(
            self.alert_referencing_unused_dataset.datasets.first().gbif_dataset_key,
            "50c9509d-22c7-4a22-a47d-8c48425ef4a7",
        )
