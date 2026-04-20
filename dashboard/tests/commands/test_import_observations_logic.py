"""Import-pipeline tests that drive run_import with in-memory rows.

Tests here do NOT use a DwCA zip file. Real-DwCA tests live in
test_import_observations.py (to be renamed to test_import_observations_dwca.py
once all logic tests are migrated).
"""

import pytest

from dashboard.models import Observation, Species
from dashboard.tests.commands.factories import make_raw_row, run_import_with_rows

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.sequential]


def test_run_import_with_rows_sanity():
    """One valid row in -> one Observation out. Confirms factories.py is
    wired correctly to run_import and the pipeline handles a trivial case."""
    Species.objects.all().delete()
    Species.objects.create(name="Lixus bardanae", gbif_taxon_key=1224034)

    run_import_with_rows([make_raw_row(gbif_id=42, occurrence_id="sanity-1")])

    assert Observation.objects.count() == 1
    obs = Observation.objects.get()
    assert obs.occurrence_id == "sanity-1"
    assert obs.gbif_id == "42"  # gbif_id is stored as a string on Observation
