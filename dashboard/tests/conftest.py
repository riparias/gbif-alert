"""Fixtures shared across the dashboard test suite."""

import datetime

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.utils import timezone

from dashboard.models import (
    Area,
    BasisOfRecord,
    DataImport,
    Dataset,
    Observation,
    Species,
)


@pytest.fixture
def observations_and_areas():
    di = DataImport.objects.create(start=timezone.now())
    dataset = Dataset.objects.create(name="D", gbif_dataset_key="k")
    basis = BasisOfRecord.objects.create(name="HUMAN_OBSERVATION")
    species = Species.objects.create(name="Procambarus fallax", gbif_taxon_key=8879526)

    # A grid of points, some inside each area, some outside, some exactly on a
    # border (4.4 is the shared edge of `square` below).
    coords = [
        (4.35, 50.65),  # inside square
        (4.40, 50.65),  # exactly on square's right edge
        (4.45, 50.65),  # outside square, inside wide
        (9.00, 50.65),  # outside everything
    ]
    for i, (lon, lat) in enumerate(coords):
        Observation.objects.create(
            gbif_id=i,
            occurrence_id=str(i),
            species=species,
            date=datetime.date.today(),
            data_import=di,
            initial_data_import=di,
            source_dataset=dataset,
            location=Point(lon, lat, srid=4326),
            basis_of_record=basis,
        )

    square = Area.objects.create(
        name="Square",
        mpoly=MultiPolygon(
            Polygon(((4.3, 50.6), (4.4, 50.6), (4.4, 50.7), (4.3, 50.7), (4.3, 50.6))),
            srid=4326,
        ),
    )
    wide = Area.objects.create(
        name="Wide",
        mpoly=MultiPolygon(
            Polygon(((4.0, 50.0), (5.0, 50.0), (5.0, 51.0), (4.0, 51.0), (4.0, 50.0))),
            srid=4326,
        ),
    )
    # A self-intersecting ("bowtie") polygon: 5 such areas exist in production
    # and they are the likeliest place for old and new to diverge.
    invalid = Area.objects.create(
        name="Bowtie",
        mpoly=MultiPolygon(
            Polygon(((4.3, 50.6), (4.5, 50.7), (4.3, 50.7), (4.5, 50.6), (4.3, 50.6))),
            srid=4326,
        ),
    )
    # Every value is an Area: the multi-area tests filter on
    # `observations_and_areas.values()`.
    return {"square": square, "wide": wide, "invalid": invalid}
