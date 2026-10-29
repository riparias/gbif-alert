"""Populate a GBIF Alert instance with species tags and Belgian areas.

Meant for the devel instance, whose species start untagged and which has no
areas, so the species and area pickers have something to narrow. It talks to
API v2 with an operator's API token, so it works against any deployed
instance; the geometries come from source_data/public_areas.

Safe to re-run: tags are merged into the current ones, and an area is skipped
when a shared area of that name already exists.

Usage:
    GBIF_ALERT_API_TOKEN=<token> uv run python scripts/populate_demo_data.py [--base-url URL]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_DIR / "source_data" / "public_areas"

# Only so GeoDjango's GDAL bindings pick up GDAL_LIBRARY_PATH from .env (on
# macOS the library is not found otherwise): no django.setup(), no database.
sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.settings")

from django.contrib.gis.gdal import DataSource  # noqa: E402

TIMEOUT = 60  # seconds; the largest area payload is ~1 MB

SPECIES_TAGS: dict[str, list[str]] = {
    "Crassula helmsii": ["plant"],
    "Myriophyllum aquaticum": ["plant"],
    "Zizania latifolia": ["plant"],
    "Lithobates catesbeianus": ["amphibian"],
    "Xenopus laevis": ["amphibian"],
    "Procambarus clarkii": ["crayfish"],
    "Procambarus virginalis": ["crayfish"],
    "Misgurnus mohoity": ["fish"],
}

# NAME_1 in the GADM-derived files -> the region tag the river basins use.
REGIONS = {"Bruxelles": "Brussels", "Vlaanderen": "Flanders", "Wallonie": "Wallonia"}

# One shared area per feature. Names and tags follow the load_*_areas commands.
AREA_SOURCES: list[dict] = [
    {
        "path": "belgian_regions/belgian_regions.shp",
        "name_field": "NAME_1",
        "tags": ["Belgium", "region"],
        "extra_tags": lambda feature: [REGIONS[feature["NAME_1"].value]],
    },
    {
        "path": "belgian_provinces/belgian_provinces.shp",
        "name_field": "NAME_2",
        "tags": ["Belgium", "province"],
        "extra_tags": lambda feature: [REGIONS[feature["NAME_1"].value]],
        # Brussels is a region, not a province: same shape and same name as the
        # region area, and two shared areas may not share a name.
        "skip": {"Bruxelles"},
    },
    {
        "path": "Riparias_Official_StudyArea.geojson",
        "name_field": "BEKNAAM",
        "tags": ["RIPARIAS", "study area"],
    },
    {
        "path": "flemish_river_basins/Wsbekken.shp",
        "name_field": "BEKNAAM",
        "tags": ["Flanders", "river basin"],
        "extra_tags": lambda feature: [feature["STRMGEB"].value],
    },
    {
        "path": "wallonia_river_basins/river_basins_wallonia.gpkg",
        "name_field": "river_basin",
        "tags": ["Wallonia", "river basin"],
    },
]


def check(response: requests.Response) -> requests.Response:
    """Stop with the API's error body (raise_for_status would drop the detail)."""
    if not response.ok:
        sys.exit(
            f"{response.request.method} {response.url} -> "
            f"{response.status_code}: {response.text}"
        )
    return response


def tag_species(session: requests.Session, api: str) -> None:
    species_by_name = {
        s["scientificName"]: s
        for s in check(session.get(f"{api}/species/", timeout=TIMEOUT)).json()
    }
    for name, tags in SPECIES_TAGS.items():
        species = species_by_name.get(name)
        if species is None:
            print(f"Species {name}: not on this instance, skipped")
            continue
        # PATCH replaces the whole tag set, so send the current tags as well.
        merged = sorted(set(species["tags"]) | set(tags))
        if merged == sorted(species["tags"]):
            print(f"Species {name}: already tagged")
            continue
        check(
            session.patch(
                f"{api}/species/{species['id']}/",
                json={"tags": merged},
                timeout=TIMEOUT,
            )
        )
        print(f"Species {name}: tags {merged}")


def create_areas(session: requests.Session, api: str) -> None:
    existing = {
        a["name"]
        for a in check(session.get(f"{api}/areas/", timeout=TIMEOUT)).json()
        if not a["isUserSpecific"]
    }
    for source in AREA_SOURCES:
        for feature in DataSource(str(SOURCE_DIR / source["path"]))[0]:
            name = feature[source["name_field"]].value
            if name in source.get("skip", ()):
                continue
            if name in existing:
                print(f"Area {name}: already there, skipped")
                continue
            tags = source["tags"] + source.get("extra_tags", lambda _: [])(feature)
            geometry = json.loads(feature.geom.transform(4326, clone=True).json)
            check(
                session.post(
                    f"{api}/areas/",
                    json={
                        "name": name,
                        "geojson": geometry,
                        "shared": True,
                        "tags": tags,
                    },
                    timeout=TIMEOUT,
                )
            )
            print(f"Area {name}: created, tags {tags}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="https://devel.gbif-alert.org")
    args = parser.parse_args()

    token = os.environ.get("GBIF_ALERT_API_TOKEN")
    if not token:
        sys.exit("Set GBIF_ALERT_API_TOKEN to an operator's API token.")

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    api = f"{args.base_url.rstrip('/')}/api/v2"

    tag_species(session, api)
    create_areas(session, api)


if __name__ == "__main__":
    main()
