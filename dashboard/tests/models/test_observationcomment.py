import datetime

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from dashboard.models import (
    User,
    DataImport,
    Observation,
    Species,
    Dataset,
    ObservationComment,
)

SEPTEMBER_13_2021 = datetime.datetime.strptime("2021-09-13", "%Y-%m-%d").date()


# @override_settings(
#     STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
# )
class ObservationCommentTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.jason = User.objects.create_user(
            username="jasonlytle",
            password="am180",
            first_name="Jason",
            last_name="Lytle",
            email="jason@grandaddy.com",
        )

        di = DataImport.objects.create(start=timezone.now())

        cls.observation = Observation.objects.create(
            gbif_id=1,
            occurrence_id="1",
            species=Species.objects.create(
                name="Procambarus fallax", gbif_taxon_key=8879526, group="CR"
            ),
            date=SEPTEMBER_13_2021,
            data_import=di,
            initial_data_import=di,
            source_dataset=Dataset.objects.create(
                name="Test dataset",
                gbif_dataset_key="4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
            ),
            location=Point(5.09513, 50.48941, srid=4326),  # Andenne
        )

        # No ObservationView created in setupTestData(): at the beginning of test_* methods, the observation is unseen

        # The user has a comment on the observation, it should be emptied upon deletion
        cls.jasons_comment = ObservationComment.objects.create(
            observation=cls.observation,
            author=cls.jason,
            text="I love this observation!",
        )

    def test_comment_can_be_emptied(self):
        """Test that a comment can be emptied via the make_empty() method"""
        self.assertEqual(self.jasons_comment.author, self.jason)
        self.assertEqual(self.jasons_comment.text, "I love this observation!")
        self.assertFalse(self.jasons_comment.emptied_because_author_deleted_account)

        self.jasons_comment.make_empty()

        # After deletion, the comment should be emptied
        self.jasons_comment.refresh_from_db()
        self.assertEqual(self.jasons_comment.author, None)
        self.assertEqual(self.jasons_comment.text, "")
        self.assertTrue(self.jasons_comment.emptied_because_author_deleted_account)
