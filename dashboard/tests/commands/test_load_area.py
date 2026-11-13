import json

import pytest
from django.core.management import call_command

from dashboard.models import Area


@pytest.mark.django_db
def test_load_area_creates_one_public_area_per_feature(tmp_path):
    """load_area reads any vector file given by path, names areas from --name-field,
    and stores plain Polygons in the MultiPolygon field. The geometry type is detected
    from the layer, so no per-file mapping is needed anymore (the hardcoded RIPARIAS
    mapping was removed together with the instance data, issue #364)."""
    square = [[[4.3, 50.6], [4.4, 50.6], [4.4, 50.7], [4.3, 50.7], [4.3, 50.6]]]
    features = [
        {
            "type": "Feature",
            "properties": {"NAAM": name},
            "geometry": {"type": "Polygon", "coordinates": square},
        }
        for name in ("Alpha", "Beta")
    ]
    path = tmp_path / "areas.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))

    call_command("load_area", str(path), "--name-field", "NAAM")

    areas = Area.objects.order_by("name")
    assert [a.name for a in areas] == ["Alpha", "Beta"]
    assert all(a.owner is None and a.mpoly.num_geom == 1 for a in areas)
