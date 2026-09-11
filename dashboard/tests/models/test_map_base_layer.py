import pytest
from django.core.exceptions import ValidationError

from dashboard.models import MapBaseLayer


def _xyz(**kwargs) -> MapBaseLayer:
    defaults = {
        "name": "OSM HOT",
        "layer_type": MapBaseLayer.XYZ,
        "url": "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
    }
    return MapBaseLayer(**{**defaults, **kwargs})


def _wms(**kwargs) -> MapBaseLayer:
    defaults = {
        "name": "National orthophotos",
        "layer_type": MapBaseLayer.WMS,
        "url": "https://example.org/geoserver/wms",
        "wms_layers": "ortho:2024",
    }
    return MapBaseLayer(**{**defaults, **kwargs})


def test_a_valid_xyz_layer_passes_validation():
    _xyz().full_clean()


@pytest.mark.parametrize(
    "url",
    [
        "https://tiles.example.org/road/{z}/{x}/{y}.png",
        # {-y} is the TMS ordering OpenLayers also understands.
        "https://tiles.example.org/road/{z}/{x}/{-y}.png",
    ],
)
def test_xyz_accepts_both_tile_row_orderings(url):
    _xyz(url=url).full_clean()


@pytest.mark.parametrize(
    "url",
    [
        "https://tiles.example.org/road/tiles.png",
        "https://tiles.example.org/road/{z}/{x}.png",  # no row
        "https://tiles.example.org/road/{x}/{y}.png",  # no zoom
    ],
)
def test_xyz_rejects_a_url_without_the_tile_placeholders(url):
    with pytest.raises(ValidationError) as excinfo:
        _xyz(url=url).full_clean()

    assert "url" in excinfo.value.message_dict


def test_xyz_rejects_the_retina_placeholder():
    # OpenLayers has no {r}; a URL copied verbatim from a provider's docs would
    # request a literal "{r}" and 404 on every tile.
    with pytest.raises(ValidationError) as excinfo:
        _xyz(url="https://tiles.example.org/road/{z}/{x}/{y}{r}.png").full_clean()

    assert "url" in excinfo.value.message_dict


def test_a_valid_wms_layer_passes_validation():
    _wms().full_clean()


def test_wms_requires_layer_names():
    with pytest.raises(ValidationError) as excinfo:
        _wms(wms_layers="").full_clean()

    assert "wms_layers" in excinfo.value.message_dict


def test_wms_rejects_a_tile_url_template():
    with pytest.raises(ValidationError) as excinfo:
        _wms(url="https://example.org/geoserver/wms/{z}/{x}/{y}.png").full_clean()

    assert "url" in excinfo.value.message_dict


def test_layer_names_are_ignored_on_an_xyz_layer():
    # Left over from switching a row's type in the admin: harmless, not an error.
    _xyz(wms_layers="ortho:2024").full_clean()


@pytest.mark.django_db
def test_layers_are_ordered_by_display_order():
    # The seed migration already filled the table, so compare on our own rows.
    MapBaseLayer.objects.all().delete()
    third = MapBaseLayer.objects.create(
        name="Third", url="u/{z}/{x}/{y}", display_order=20
    )
    first = MapBaseLayer.objects.create(
        name="First", url="u/{z}/{x}/{y}", display_order=0
    )
    second = MapBaseLayer.objects.create(
        name="Second", url="u/{z}/{x}/{y}", display_order=10
    )

    assert list(MapBaseLayer.objects.all()) == [first, second, third]


@pytest.mark.django_db
def test_enabled_returns_only_enabled_layers_in_order():
    MapBaseLayer.objects.all().delete()
    MapBaseLayer.objects.create(
        name="Hidden", url="u/{z}/{x}/{y}", display_order=0, is_enabled=False
    )
    shown = MapBaseLayer.objects.create(
        name="Shown", url="u/{z}/{x}/{y}", display_order=10
    )

    assert list(MapBaseLayer.objects.enabled()) == [shown]


@pytest.mark.django_db
def test_to_dict_of_an_xyz_layer():
    layer = MapBaseLayer.objects.create(
        name="ESRI World Imagery",
        url="https://example.org/{z}/{y}/{x}",
        attribution="Esri",
        max_zoom=19,
    )

    assert layer.to_dict() == {
        "id": layer.pk,
        "name": "ESRI World Imagery",
        "type": "xyz",
        "url": "https://example.org/{z}/{y}/{x}",
        "wmsLayers": "",
        "attribution": "Esri",
        "maxZoom": 19,
    }
