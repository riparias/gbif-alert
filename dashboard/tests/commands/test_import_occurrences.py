import datetime
from pathlib import Path

import requests_mock
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone

from dashboard.models import (
    Species,
    DataImport,
    Occurrence,
    Dataset,
    OccurrenceComment,
    User,
)

THIS_SCRIPT_PATH = Path(__file__).parent
SAMPLE_DATA_PATH = THIS_SCRIPT_PATH / "sample_data"


class ImportOccurrencesTest(TransactionTestCase):
    def setUp(self) -> None:
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

        # This occurrence will be replaced during the import process
        # because there's a row with the same occurrence_id and dataset_key in the DwC-A
        occurrence_to_be_replaced = Occurrence.objects.create(
            gbif_id=1,
            occurrence_id="https://www.inaturalist.org/observations/33366292",
            source_dataset=inaturalist,
            species=self.polydrusus,
            date=datetime.date.today() - datetime.timedelta(days=1),
            data_import=DataImport.objects.create(start=timezone.now()),
            location=Point(5.09513, 50.48941, srid=4326),
        )

        # This one has no equivalent in the DwC-A
        occurrence_not_replaced = Occurrence.objects.create(
            gbif_id=2,
            occurrence_id="2",
            source_dataset=inaturalist,
            species=self.lixus,
            date=datetime.date.today(),
            data_import=DataImport.objects.create(start=timezone.now()),
            location=Point(5.09513, 50.48941, srid=4326),
        )

        comment_author = User.objects.create_user(
            username="testuser",
            password="12345",
            first_name="John",
            last_name="Frusciante",
            email="frusciante@gmail.com",
        )

        OccurrenceComment.objects.create(
            author=comment_author,
            occurrence=occurrence_to_be_replaced,
            text="This is a comment to migrate",
        )

    def test_ignore_unusable_occurrences(self) -> None:
        """The DwC-A contains 12 records, but some are not usable:

        - missing coordinates: 3 records
        - no year: 1 record
        - no occurrence ID: 1 record

        => so, only 7 should be loaded after the import process
        """

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_occurrences", source_dwca=gbif_download_file)

        self.assertEqual(Occurrence.objects.all().count(), 7)
        # TODO: more testing to make sure it's the usable ones that were loaded?

    def test_load_occurrence_values(self) -> None:
        """Imported values look correct"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_occurrences", source_dwca=gbif_download_file)

        occurrences = Occurrence.objects.all().order_by("id")
        # We assume occurrences are loaded in the DwC-A rows order
        occ = occurrences[0]  #
        self.assertEqual(str(occ.date), "2020-04-20")
        self.assertEqual(occ.gbif_id, "3044795455")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/42671325",
        )
        self.assertEqual(occ.stable_id, "4aa3b8d81c4a62c89b73a4416af7d51968c29104")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 3.315567)
        self.assertAlmostEqual(lat, 51.354473)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(occ.source_dataset.name, "iNaturalist")

        occ = occurrences[1]
        self.assertEqual(str(occ.date), "2020-04-19")
        self.assertEqual(occ.gbif_id, "2609350465")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/42577016",
        )
        self.assertEqual(occ.stable_id, "6a6fc5bd50d1ead0f33f32c843b185bbfbd7c166")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 3.254023)
        self.assertAlmostEqual(lat, 50.664364)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(occ.source_dataset.name, "iNaturalist")

        occ = occurrences[
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
        self.assertAlmostEqual(lon, 3.52526)
        self.assertAlmostEqual(lat, 51.150846)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(occ.source_dataset.name, "iNaturalist")

        occ = occurrences[3]

        self.assertEqual(str(occ.date), "2018-09-05")
        self.assertEqual(occ.gbif_id, "1914197587")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/16227955",
        )
        self.assertEqual(occ.stable_id, "48f6d956f104c4c83174e9ea7cbb0b545e995d4d")
        self.assertEqual(occ.species_id, self.lixus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 4.360086)
        self.assertAlmostEqual(lat, 50.646894)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(occ.source_dataset.name, "iNaturalist")

        occ = occurrences[4]

        self.assertEqual(str(occ.date), "2018-05-11")
        self.assertEqual(occ.gbif_id, "1847507314")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/12411012",
        )
        self.assertEqual(occ.stable_id, "baddab78a96bf75f3dd98b0be69b035364f6a77e")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 2.59858)
        self.assertAlmostEqual(lat, 51.097573)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(occ.source_dataset.name, "iNaturalist")

        occ = occurrences[5]

        self.assertEqual(str(occ.date), "2017-05-15")
        self.assertEqual(occ.gbif_id, "1802743867")
        self.assertEqual(
            occ.occurrence_id,
            "https://www.inaturalist.org/observations/9294095",
        )
        self.assertEqual(occ.stable_id, "85b4076d572cdc8782746d3dc0252fab7e2a5cd2")
        self.assertEqual(occ.species_id, self.polydrusus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 4.454613)
        self.assertAlmostEqual(lat, 51.26503)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(occ.source_dataset.name, "iNaturalist")

        occ = occurrences[6]

        self.assertEqual(str(occ.date), "1950-06-18")
        self.assertEqual(occ.gbif_id, "1315928743")
        self.assertEqual(
            occ.occurrence_id,
            "Ugent:UGMD:16879",
        )
        self.assertEqual(occ.stable_id, "cc478993ca998a9be116bad94e6b31ddf2128f33")
        self.assertEqual(occ.species_id, self.lixus.pk)
        lon, lat = occ.lonlat_4326_tuple
        self.assertAlmostEqual(lon, 4.418141)
        self.assertAlmostEqual(lat, 51.27734)
        self.assertEqual(occ.data_import_id, DataImport.objects.latest("id").id)
        self.assertEqual(
            occ.source_dataset.name,
            "Ghent university - Zoology Museum - Insect Collection",
        )
        # We stop there, the remaining rows in DwC-A miss either the location or the occurence id

    def test_occurrence_comments_migrated(self) -> None:
        comment = OccurrenceComment.objects.all()[0]  # there's only one...
        previous_occurrence_id = comment.occurrence_id
        previous_stable_id = comment.occurrence.stable_id

        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_occurrences", source_dwca=gbif_download_file)

        comment.refresh_from_db()
        self.assertNotEqual(comment.occurrence_id, previous_occurrence_id)
        self.assertEqual(comment.occurrence.stable_id, previous_stable_id)

    def test_old_occurrences_deleted(self) -> None:
        """The old occurrences (replaced and not replaced) are deleted from the database after a new import"""
        id_occurrences_before = list(
            Occurrence.objects.all().values_list("id", flat=True)
        )
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_occurrences", source_dwca=gbif_download_file)

        id_occurrences_after = list(
            Occurrence.objects.all().values_list("id", flat=True)
        )
        self.assertFalse(bool(set(id_occurrences_before) & set(id_occurrences_after)))

    def test_dataimport_object_created(self) -> None:
        count_before = DataImport.objects.count()
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_occurrences", source_dwca=gbif_download_file)

        self.assertEqual(DataImport.objects.count(), count_before + 1)

    def test_dataimport_object_values(self):
        """Values of the DataImport object are created

        Side effect of the occurrence_counter check: we also check that newly created occurrences reference the correct
        DataImport object
        """
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            call_command("import_occurrences", source_dwca=gbif_download_file)

        di = DataImport.objects.latest("id")
        self.assertIsNotNone(di.start)
        self.assertIsNotNone(di.end)
        self.assertGreater(di.end, di.start)
        self.assertTrue(di.completed)
        self.assertEqual(di.gbif_download_id, "0076720-210914110416597")
        self.assertEqual(
            di.imported_occurrences_counter,
            Occurrence.objects.filter(data_import=di).count(),
        )

    def test_gbif_request_not_necessary(self) -> None:
        """No HTTP request emitted if the --source-dwca option is used"""
        with open(SAMPLE_DATA_PATH / "gbif_download.zip", "rb") as gbif_download_file:
            with requests_mock.Mocker() as m:
                call_command(
                    "import_occurrences",
                    source_dwca=gbif_download_file,
                )
                request_history = m.request_history
                self.assertEqual(len(request_history), 0)

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

                call_command("import_occurrences")

                request_history = m.request_history

                # 1. A request for a new download wirth the correct filters was sent first
                self.assertEqual(request_history[0].method, "POST")
                self.assertEqual(
                    request_history[0].url,
                    "https://api.gbif.org/v1/occurrence/download/request",
                )
                self.assertEqual(
                    request_history[0].text,
                    '{"predicate": {"type": "and", "predicates": [{"type": "equals", "key": "COUNTRY", "value": "BE"}, {"type": "in", "key": "TAXON_KEY", "values": ["1224034", "7972617"]}]}}',
                )

                # 2. A request to download the DwCA file was subsequently emitted
                self.assertEqual(request_history[1].method, "GET")
                self.assertEqual(
                    request_history[1].url,
                    "https://api.gbif.org/v1/occurrence/download/request/1000",
                )
