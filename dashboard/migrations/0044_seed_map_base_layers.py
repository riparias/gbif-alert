from django.db import migrations

# The three layers GBIF Alert hardcoded until now, so an instance that is happy
# with them needs no operator action. Stamen Toner is deliberately not among
# them: Stadia Maps answers 401 for any domain that is not registered with
# them, so it only ever worked on localhost and on alert.riparias.be. ESRI Light
# Gray Canvas replaces it in the same role - a desaturated backdrop that lets the
# observation hexagons stand out. (CartoDB Positron was tried first, but its
# tiles now come back watermarked "API KEY REQUIRED" without an account.)
SEEDED_LAYERS = [
    {
        "name": "OSM HOT",
        "url": "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        "attribution": (
            "OpenStreetMap contributors, tiles by Humanitarian OpenStreetMap "
            "Team, hosted by OpenStreetMap France"
        ),
        "max_zoom": 19,
        "display_order": 0,
    },
    {
        "name": "ESRI Light Gray Canvas",
        "url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        ),
        "attribution": (
            "Esri, HERE, Garmin, OpenStreetMap contributors, and the GIS User "
            "Community"
        ),
        "max_zoom": 16,
        "display_order": 10,
    },
    {
        "name": "ESRI World Imagery",
        "url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "attribution": "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        "max_zoom": 19,
        "display_order": 20,
    },
]


def seed_map_base_layers(apps, schema_editor):
    MapBaseLayer = apps.get_model("dashboard", "MapBaseLayer")
    for layer in SEEDED_LAYERS:
        MapBaseLayer.objects.create(layer_type="xyz", **layer)


def delete_map_base_layers(apps, schema_editor):
    MapBaseLayer = apps.get_model("dashboard", "MapBaseLayer")
    MapBaseLayer.objects.filter(
        name__in=[layer["name"] for layer in SEEDED_LAYERS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0043_mapbaselayer"),
    ]

    operations = [
        migrations.RunPython(seed_map_base_layers, delete_map_base_layers),
    ]
