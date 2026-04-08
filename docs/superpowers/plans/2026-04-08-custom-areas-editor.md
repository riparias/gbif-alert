# Custom Areas Map Editor - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-page polygon drawing/editing interface at `/my-custom-areas/new` and `/my-custom-areas/:id/edit`, backed by two new Django Ninja API endpoints.

**Architecture:** A single `AreaEditorPage.vue` handles both create and edit modes (determined by the presence of `:id` in the route). It creates its own OpenLayers map, uses a shared `useBaseLayer` composable for background switching, and manages a `VectorSource` of individual `Feature<Polygon>` objects. On save it serialises these to a GeoJSON FeatureCollection and POSTs/PATCHes the appropriate API endpoint.

**Tech Stack:** Vue 3 Composition API, PrimeVue, Vue Router, OpenLayers (ol), Django Ninja, Django GIS (GEOSGeometry), pytest + Playwright for tests.

**Spec:** `docs/superpowers/specs/2026-04-08-custom-areas-editor-design.md`

---

## File Map

**New files:**
- `dashboard/tests/various/test_api_areas.py` - Django TestCase for new API endpoints
- `assets/frontend/composables/useBaseLayer.ts` - extracted base layer logic
- `assets/frontend/pages/AreaEditorPage.vue` - the new editor page

**Modified files:**
- `dashboard/geo_utils.py` - add `geojson_to_multipolygon()`
- `dashboard/api_v2_schemas.py` - add `AreaFromDrawingIn`, `AreaPatchIn`
- `dashboard/api_v2.py` - add `POST /areas/from-drawing/`, `PATCH /areas/{id}/`
- `assets/frontend/types/api.ts` - regenerated (do not edit by hand)
- `assets/frontend/components/BaseMap.vue` - use `useBaseLayer` composable
- `assets/frontend/router/index.ts` - two new routes
- `assets/frontend/translations.ts` - new i18n keys (en, fr, nl)
- `assets/frontend/pages/UserAreasPage.vue` - add "Draw area" button
- `assets/frontend/components/AreaCard.vue` - add "Edit" button
- `dashboard/tests/playwright/test_areas.py` - add editor E2E tests

---

## Task 1: `geojson_to_multipolygon()` in `geo_utils.py`

**Files:**
- Create: `dashboard/tests/various/test_api_areas.py`
- Modify: `dashboard/geo_utils.py`

- [ ] **Step 1: Write failing tests**

Create `dashboard/tests/various/test_api_areas.py`:

```python
import json

from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase

from dashboard.geo_utils import geojson_to_multipolygon


SINGLE_POLYGON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            },
            "properties": {},
        }
    ],
}

TWO_POLYGON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            },
            "properties": {},
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[10.0, 50.0], [10.0, 51.0], [11.0, 51.0], [10.0, 50.0]]],
            },
            "properties": {},
        },
    ],
}

MULTIPOLYGON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
                    [[[10.0, 50.0], [10.0, 51.0], [11.0, 51.0], [10.0, 50.0]]],
                ],
            },
            "properties": {},
        }
    ],
}


class GeoJSONToMultiPolygonTests(TestCase):
    def test_single_polygon_returns_multipolygon(self):
        result = geojson_to_multipolygon(SINGLE_POLYGON_FC)
        self.assertEqual(result.geom_type, "MultiPolygon")
        self.assertEqual(result.srid, 3857)
        self.assertEqual(len(result), 1)

    def test_two_polygon_features_merged(self):
        result = geojson_to_multipolygon(TWO_POLYGON_FC)
        self.assertEqual(result.geom_type, "MultiPolygon")
        self.assertEqual(len(result), 2)

    def test_multipolygon_feature_flattened(self):
        result = geojson_to_multipolygon(MULTIPOLYGON_FC)
        self.assertEqual(result.geom_type, "MultiPolygon")
        self.assertEqual(len(result), 2)

    def test_empty_feature_collection_raises(self):
        with self.assertRaises(ValueError):
            geojson_to_multipolygon({"type": "FeatureCollection", "features": []})

    def test_non_polygon_geometry_raises(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [4.0, 50.0]},
                    "properties": {},
                }
            ],
        }
        with self.assertRaises(ValueError):
            geojson_to_multipolygon(fc)

    def test_reprojected_to_3857(self):
        result = geojson_to_multipolygon(SINGLE_POLYGON_FC, dest_srid=3857)
        # Coordinates should be large (Web Mercator, not lon/lat)
        centroid = result.centroid
        self.assertGreater(abs(centroid.x), 1_000_000)
```

- [ ] **Step 2: Run tests to see them fail**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/test_api_areas.py -v
```

Expected: ImportError or AttributeError - `geojson_to_multipolygon` does not exist yet.

- [ ] **Step 3: Implement `geojson_to_multipolygon` in `geo_utils.py`**

Add after the existing `file_to_wkt_multipolygon` function:

```python
import json

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon as GEOSMultiPolygon


def geojson_to_multipolygon(
    geojson: dict,
    dest_srid: int = DATA_SRID,
) -> GEOSMultiPolygon:
    """Convert a GeoJSON FeatureCollection (EPSG:4326) to a GEOSMultiPolygon.

    Parameters
    ----------
    geojson : dict
        A GeoJSON FeatureCollection with Polygon or MultiPolygon features,
        in EPSG:4326. This is the format produced by the OpenLayers GeoJSON
        format class.
    dest_srid : int
        Target SRID for the returned geometry. Defaults to DATA_SRID (3857).

    Returns
    -------
    GEOSMultiPolygon
        A MultiPolygon geometry in dest_srid containing all polygons from the
        input features.

    Raises
    ------
    ValueError
        If the FeatureCollection contains no features, or contains a geometry
        type other than Polygon or MultiPolygon.
    """
    features = geojson.get("features", [])
    if not features:
        raise ValueError("GeoJSON FeatureCollection must contain at least one feature")

    polygons = []
    for feature in features:
        geom = GEOSGeometry(json.dumps(feature["geometry"]), srid=4326)
        geom.transform(dest_srid)
        if geom.geom_type == "Polygon":
            polygons.append(geom)
        elif geom.geom_type == "MultiPolygon":
            polygons.extend(list(geom))
        else:
            raise ValueError(
                f"Expected Polygon or MultiPolygon features, got {geom.geom_type}"
            )

    return GEOSMultiPolygon(*polygons, srid=dest_srid)
```

Also add `import json` at the top of `geo_utils.py` if not already present (it isn't).

- [ ] **Step 4: Run tests to see them pass**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/test_api_areas.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/geo_utils.py dashboard/tests/various/test_api_areas.py
git commit -m "feat: add geojson_to_multipolygon() to geo_utils"
```

---

## Task 2: New API schemas

**Files:**
- Modify: `dashboard/api_v2_schemas.py`

- [ ] **Step 1: Add `AreaFromDrawingIn` and `AreaPatchIn` schemas**

In `dashboard/api_v2_schemas.py`, add after the `AreaDeleteError` class:

```python
class AreaFromDrawingIn(Schema):
    name: str
    geojson: dict  # GeoJSON FeatureCollection, EPSG:4326


class AreaPatchIn(Schema):
    name: str | None = None
    geojson: dict | None = None  # None means "leave geometry unchanged"
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/api_v2_schemas.py
git commit -m "feat: add AreaFromDrawingIn and AreaPatchIn schemas"
```

---

## Task 3: `POST /api/v2/areas/from-drawing/` endpoint

**Files:**
- Modify: `dashboard/api_v2.py`
- Modify: `dashboard/tests/various/test_api_areas.py`

- [ ] **Step 1: Write failing tests**

Append to `dashboard/tests/various/test_api_areas.py`:

```python
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon


User = get_user_model()

SIMPLE_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[4.0, 50.0], [4.0, 51.0], [5.0, 51.0], [4.0, 50.0]]],
            },
            "properties": {},
        }
    ],
}


class AreaFromDrawingAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="drawer", password="pass", email="drawer@t.com"
        )
        self.client.force_login(self.user)

    def test_create_from_drawing_returns_201(self):
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "My drawn area", "geojson": SIMPLE_FC}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["name"], "My drawn area")
        self.assertTrue(data["isUserSpecific"])

    def test_create_from_drawing_requires_auth(self):
        self.client.logout()
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "Anon area", "geojson": SIMPLE_FC}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_create_from_drawing_invalid_geometry_returns_422(self):
        bad_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [4.0, 50.0]},
                    "properties": {},
                }
            ],
        }
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "Bad area", "geojson": bad_fc}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("detail", resp.json())

    def test_create_from_drawing_empty_fc_returns_422(self):
        empty_fc = {"type": "FeatureCollection", "features": []}
        resp = self.client.post(
            "/api/v2/areas/from-drawing/",
            data=json.dumps({"name": "Empty", "geojson": empty_fc}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 422)
```

- [ ] **Step 2: Run tests to see them fail**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/test_api_areas.py::AreaFromDrawingAPITests -v
```

Expected: 404 or similar - endpoint does not exist yet.

- [ ] **Step 3: Add imports and implement the endpoint in `api_v2.py`**

Add `AreaFromDrawingIn` to the import from `api_v2_schemas`:

```python
from dashboard.api_v2_schemas import (
    AreaCreateError,
    AreaDeleteError,
    AreaFromDrawingIn,
    AreaOut,
    ...  # keep all existing imports
)
```

Add `geojson_to_multipolygon` to the import from `geo_utils`:

```python
from dashboard.geo_utils import file_to_wkt_multipolygon, geojson_to_multipolygon
```

Add the endpoint after the existing `area_create` function (before `area_delete_endpoint`):

```python
@api_v2.post(
    "/areas/from-drawing/",
    response={201: AreaOut, 422: AreaCreateError},
    auth=django_auth,
)
def area_create_from_drawing(request: HttpRequest, payload: AreaFromDrawingIn):
    """Create a new user-specific area from a GeoJSON FeatureCollection.

    Accepts a GeoJSON FeatureCollection (EPSG:4326) with Polygon or MultiPolygon
    features drawn by the user. All features are merged into a single MultiPolygon.

    Returns 422 with a detail message if the geometry is invalid.
    """
    user = cast(User, request.user)
    try:
        mpoly = geojson_to_multipolygon(payload.geojson)
    except ValueError as exc:
        return 422, {"detail": str(exc)}
    area = Area.objects.create(mpoly=mpoly, owner=user, name=payload.name)
    return 201, {
        "id": area.pk,
        "name": area.name,
        "isUserSpecific": area.is_user_specific,
        "tags": [],
    }
```

- [ ] **Step 4: Run tests to see them pass**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/test_api_areas.py::AreaFromDrawingAPITests -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/api_v2.py dashboard/tests/various/test_api_areas.py
git commit -m "feat: add POST /api/v2/areas/from-drawing/ endpoint"
```

---

## Task 4: `PATCH /api/v2/areas/{area_id}/` endpoint

**Files:**
- Modify: `dashboard/api_v2.py`
- Modify: `dashboard/api_v2_schemas.py`
- Modify: `dashboard/tests/various/test_api_areas.py`

- [ ] **Step 1: Write failing tests**

Append to `dashboard/tests/various/test_api_areas.py`:

```python
from dashboard.models import Area


SIMPLE_MPOLY = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)), srid=4326))


class AreaPatchAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="patcher", password="pass", email="patcher@t.com"
        )
        self.other = User.objects.create_user(
            username="other", password="pass", email="other@t.com"
        )
        self.area = Area.objects.create(
            name="Original", owner=self.user, mpoly=SIMPLE_MPOLY
        )
        self.client.force_login(self.user)

    def test_patch_name_returns_200(self):
        resp = self.client.patch(
            f"/api/v2/areas/{self.area.pk}/",
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.area.refresh_from_db()
        self.assertEqual(self.area.name, "Renamed")

    def test_patch_geometry_returns_200(self):
        resp = self.client.patch(
            f"/api/v2/areas/{self.area.pk}/",
            data=json.dumps({"name": "Original", "geojson": SIMPLE_FC}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.area.refresh_from_db()
        self.assertEqual(self.area.mpoly.geom_type, "MultiPolygon")

    def test_patch_null_geojson_leaves_geometry_unchanged(self):
        original_wkt = self.area.mpoly.wkt
        resp = self.client.patch(
            f"/api/v2/areas/{self.area.pk}/",
            data=json.dumps({"name": "New name", "geojson": None}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.area.refresh_from_db()
        self.assertEqual(self.area.mpoly.wkt, original_wkt)

    def test_patch_another_users_area_returns_404(self):
        other_area = Area.objects.create(
            name="Other area", owner=self.other, mpoly=SIMPLE_MPOLY
        )
        resp = self.client.patch(
            f"/api/v2/areas/{other_area.pk}/",
            data=json.dumps({"name": "Hijacked"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_nonexistent_area_returns_404(self):
        resp = self.client.patch(
            "/api/v2/areas/99999/",
            data=json.dumps({"name": "Ghost"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_requires_auth(self):
        self.client.logout()
        resp = self.client.patch(
            f"/api/v2/areas/{self.area.pk}/",
            data=json.dumps({"name": "Anon"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
```

- [ ] **Step 2: Run tests to see them fail**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/test_api_areas.py::AreaPatchAPITests -v
```

Expected: 405 Method Not Allowed or 404 - endpoint does not exist yet.

- [ ] **Step 3: Add `AreaPatchIn` import and implement the endpoint in `api_v2.py`**

Add `AreaPatchIn` to the schema imports:

```python
from dashboard.api_v2_schemas import (
    AreaCreateError,
    AreaDeleteError,
    AreaFromDrawingIn,
    AreaPatchIn,
    AreaOut,
    ...
)
```

Add the endpoint after `area_create_from_drawing` (before `area_delete_endpoint`):

```python
@api_v2.patch(
    "/areas/{area_id}/",
    response={200: AreaOut, 422: AreaCreateError},
    auth=django_auth,
)
def area_patch(request: HttpRequest, area_id: int, payload: AreaPatchIn):
    """Update the name and/or geometry of a user-owned area.

    Both fields are optional. Passing geojson=None leaves the geometry unchanged.
    Returns 404 if the area does not exist or belongs to another user.
    """
    area = get_object_or_404(Area, pk=area_id, owner=request.user)
    if payload.name is not None:
        area.name = payload.name
    if payload.geojson is not None:
        try:
            area.mpoly = geojson_to_multipolygon(payload.geojson)
        except ValueError as exc:
            return 422, {"detail": str(exc)}
    area.save()
    return {
        "id": area.pk,
        "name": area.name,
        "isUserSpecific": area.is_user_specific,
        "tags": [t.name for t in area.tags.all()],
    }
```

- [ ] **Step 4: Run tests to see them pass**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/test_api_areas.py::AreaPatchAPITests -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Run the full test suite to check nothing broke**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/various/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add dashboard/api_v2.py dashboard/tests/various/test_api_areas.py
git commit -m "feat: add PATCH /api/v2/areas/{id}/ endpoint"
```

---

## Task 5: Regenerate frontend TypeScript types

**Files:**
- Modify: `assets/frontend/types/api.ts` (auto-generated)

- [ ] **Step 1: Regenerate types from the updated OpenAPI schema**

```bash
cd /path/to/gbif-alert
DJANGO_SETTINGS_MODULE=djangoproject.local_settings npm run generate-types
```

Expected: `assets/frontend/types/api.ts` updated. The file header says "Do not make direct changes to the file." Verify the file changed with `git diff --stat assets/frontend/types/api.ts`.

- [ ] **Step 2: Commit**

```bash
git add assets/frontend/types/api.ts
git commit -m "chore: regenerate frontend API types after new area endpoints"
```

---

## Task 6: `useBaseLayer.ts` composable + refactor `BaseMap.vue`

**Files:**
- Create: `assets/frontend/composables/useBaseLayer.ts`
- Modify: `assets/frontend/components/BaseMap.vue`

- [ ] **Step 1: Create `useBaseLayer.ts`**

Create `assets/frontend/composables/useBaseLayer.ts`:

```typescript
import { ref, watch, markRaw } from "vue";
import TileLayer from "ol/layer/Tile";
import StadiaMaps from "ol/source/StadiaMaps";
import OSM from "ol/source/OSM";
import XYZ from "ol/source/XYZ";
import type { Map as OLMap } from "ol";

export const BASE_LAYER_OPTIONS = [
    { id: "osmHot", label: "OSM HOT" },
    { id: "toner", label: "Stamen Toner" },
    { id: "esriImagery", label: "ESRI World Imagery" },
] as const;

export function makeBaseLayer(id: string): TileLayer<any> {
    if (id === "toner") {
        return new TileLayer({ source: new StadiaMaps({ layer: "stamen_toner" }) });
    }
    if (id === "esriImagery") {
        return new TileLayer({
            source: new XYZ({
                url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                maxZoom: 19,
            }),
        });
    }
    return new TileLayer({
        source: new OSM({ url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png" }),
    });
}

/**
 * Composable that manages the base tile layer of an OpenLayers map.
 *
 * Usage:
 *   const { selectedBaseLayerId, attachToMap } = useBaseLayer();
 *   // In onMounted, after creating olMap:
 *   attachToMap(olMap);
 */
export function useBaseLayer() {
    const selectedBaseLayerId = ref<string>("osmHot");

    function attachToMap(olMap: OLMap): void {
        watch(selectedBaseLayerId, (newId) => {
            const layers = olMap.getLayers();
            layers.removeAt(0);
            layers.insertAt(0, markRaw(makeBaseLayer(newId)));
        });
    }

    return { selectedBaseLayerId, attachToMap };
}
```

- [ ] **Step 2: Refactor `BaseMap.vue` to use the composable**

Replace the `<script setup>` block in `assets/frontend/components/BaseMap.vue` with:

```typescript
import { ref, onMounted, onUnmounted, markRaw } from "vue";
import { useI18n } from "vue-i18n";
import { Map as OLMap, View } from "ol";
import { fromLonLat } from "ol/proj";
import Select from "primevue/select";
import "ol/ol.css";
import { useBaseLayer, makeBaseLayer, BASE_LAYER_OPTIONS } from "../composables/useBaseLayer";

const props = withDefaults(
    defineProps<{
        height?: string;
        initialLon?: number;
        initialLat?: number;
        initialZoom?: number;
    }>(),
    {
        height: "480px",
        initialLon: 0,
        initialLat: 20,
        initialZoom: 2,
    }
);

const { t } = useI18n();
const { selectedBaseLayerId, attachToMap } = useBaseLayer();
const mapEl = ref<HTMLElement | null>(null);
let olMap: OLMap | null = null;

onMounted(() => {
    olMap = markRaw(
        new OLMap({
            target: mapEl.value!,
            layers: [markRaw(makeBaseLayer("osmHot"))],
            view: new View({
                zoom: props.initialZoom,
                center: fromLonLat([props.initialLon, props.initialLat]),
            }),
        })
    );
    attachToMap(olMap);
});

onUnmounted(() => {
    olMap?.setTarget(undefined);
    olMap = null;
});

defineExpose({ getOlMap: () => olMap });
```

The `<template>` and `<style>` blocks are unchanged - leave them exactly as they are. The only change is in `<script setup>`: remove the local `BASE_LAYER_OPTIONS`, `makeBaseLayer`, `selectedBaseLayerId`, and `watch` and replace with the composable.

- [ ] **Step 3: Run mypy**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m mypy assets/frontend/composables/useBaseLayer.ts 2>/dev/null || npx vue-tsc --noEmit
```

(If the project uses vue-tsc for type checking, use that. Otherwise just verify the dev server builds without errors in the next step.)

- [ ] **Step 4: Verify the map still works**

```bash
npm run dev
```

Open `/my-custom-areas` in the browser. The area cards should still show maps with the base layer switcher working. Cancel with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add assets/frontend/composables/useBaseLayer.ts assets/frontend/components/BaseMap.vue
git commit -m "refactor: extract useBaseLayer composable from BaseMap.vue"
```

---

## Task 7: Router routes + translation keys

**Files:**
- Modify: `assets/frontend/router/index.ts`
- Modify: `assets/frontend/translations.ts`

- [ ] **Step 1: Add two routes to `router/index.ts`**

In `assets/frontend/router/index.ts`, add after the `/my-custom-areas` route:

```typescript
{ path: "/my-custom-areas/new", component: () => import("../pages/AreaEditorPage.vue") },
{ path: "/my-custom-areas/:id/edit", component: () => import("../pages/AreaEditorPage.vue") },
```

The file should look like:

```typescript
{ path: "/my-custom-areas", component: () => import("../pages/UserAreasPage.vue") },
{ path: "/my-custom-areas/new", component: () => import("../pages/AreaEditorPage.vue") },
{ path: "/my-custom-areas/:id/edit", component: () => import("../pages/AreaEditorPage.vue") },
```

- [ ] **Step 2: Add translation keys - English (`en` section, around line 162)**

In `assets/frontend/translations.ts`, add after the `areaCreated` key in the `en` section:

```typescript
drawArea: "Draw area",
editArea: "Edit",
drawingTool: "Drawing tool",
drawPolygon: "Draw polygon",
editVertices: "Edit vertices",
deletePolygon: "Delete polygon",
deleteAreaButton: "Delete area",
unsavedChanges: "Unsaved changes",
clickToStartDrawing: "Click on the map to start drawing",
confirmDeletePolygon: "Delete this polygon?",
polygonCount: "{count} polygon(s) in this area",
areaSaved: "Area saved",
unexpectedError: "An unexpected error occurred",
```

- [ ] **Step 3: Add translation keys - French (`fr` section, around line 396)**

In the `fr` section, add after the `areaCreated` key:

```typescript
drawArea: "Dessiner une zone",
editArea: "Modifier",
drawingTool: "Outil de dessin",
drawPolygon: "Dessiner un polygone",
editVertices: "Modifier les sommets",
deletePolygon: "Supprimer le polygone",
deleteAreaButton: "Supprimer la zone",
unsavedChanges: "Modifications non sauvegardees",
clickToStartDrawing: "Cliquez sur la carte pour commencer a dessiner",
confirmDeletePolygon: "Supprimer ce polygone ?",
polygonCount: "{count} polygone(s) dans cette zone",
areaSaved: "Zone sauvegardee",
unexpectedError: "Une erreur inattendue s'est produite",
```

- [ ] **Step 4: Add translation keys - Dutch (`nl` section, around line 631)**

In the `nl` section, add after the `areaCreated` key:

```typescript
drawArea: "Gebied tekenen",
editArea: "Bewerken",
drawingTool: "Tekentool",
drawPolygon: "Polygoon tekenen",
editVertices: "Hoekpunten bewerken",
deletePolygon: "Polygoon verwijderen",
deleteAreaButton: "Gebied verwijderen",
unsavedChanges: "Niet-opgeslagen wijzigingen",
clickToStartDrawing: "Klik op de kaart om te beginnen met tekenen",
confirmDeletePolygon: "Dit polygoon verwijderen?",
polygonCount: "{count} polygoon/polygonen in dit gebied",
areaSaved: "Gebied opgeslagen",
unexpectedError: "Er is een onverwachte fout opgetreden",
```

- [ ] **Step 5: Commit**

```bash
git add assets/frontend/router/index.ts assets/frontend/translations.ts
git commit -m "feat: add editor routes and i18n keys for area editor"
```

---

## Task 8: Update `UserAreasPage.vue` and `AreaCard.vue`

**Files:**
- Modify: `assets/frontend/pages/UserAreasPage.vue`
- Modify: `assets/frontend/components/AreaCard.vue`

- [ ] **Step 1: Add "Draw area" button to `UserAreasPage.vue`**

Add `useRouter` import and a "Draw area" button alongside the existing "New area" (upload) button.

Replace the `<script setup>` imports section to add the router:

```typescript
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import ProgressSpinner from "primevue/progressspinner";
import AreaCard from "../components/AreaCard.vue";
import AreaUploadDialog from "../components/AreaUploadDialog.vue";
import type { components } from "../types/api";
```

Add `const router = useRouter();` after `const { t } = useI18n();`.

In the template, replace the single button in `.page-header` with two buttons:

```html
<div class="page-header">
    <h1>{{ t("message.navMyCustomAreas") }}</h1>
    <div style="display: flex; gap: 0.5rem;">
        <Button
            :label="t('message.drawArea')"
            icon="pi pi-pencil"
            severity="secondary"
            @click="router.push('/my-custom-areas/new')"
        />
        <Button
            :label="t('message.newArea')"
            icon="pi pi-upload"
            @click="showUploadDialog = true"
        />
    </div>
</div>
```

- [ ] **Step 2: Add "Edit" button to `AreaCard.vue`**

Add `useRouter` to the imports:

```typescript
import { useRouter } from "vue-router";
```

Add `const router = useRouter();` after `const toast = useToast();`.

In the template, add an Edit button alongside the existing Delete button:

```html
<div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
    <Button
        :label="t('message.editArea')"
        icon="pi pi-pencil"
        severity="secondary"
        size="small"
        @click="router.push(`/my-custom-areas/${props.area.id}/edit`)"
    />
    <Button
        :label="t('message.deleteArea')"
        icon="pi pi-trash"
        severity="danger"
        size="small"
        @click="confirmDelete"
    />
</div>
```

Remove the standalone `<Button ... @click="confirmDelete" />` that was there before (it's now inside the flex container above).

- [ ] **Step 3: Verify in the browser**

```bash
npm run dev
```

Navigate to `/my-custom-areas`. You should see two buttons in the header ("Draw area" and "New area"), and each card should have "Edit" and "Delete this area" buttons. Clicking "Draw area" should navigate to `/my-custom-areas/new` (which will 404 until the page component is created). Cancel with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add assets/frontend/pages/UserAreasPage.vue assets/frontend/components/AreaCard.vue
git commit -m "feat: add Draw area and Edit area navigation buttons"
```

---

## Task 9: `AreaEditorPage.vue` - map shell and geometry loading

**Files:**
- Create: `assets/frontend/pages/AreaEditorPage.vue`

This task creates the page skeleton: layout, OL map, base layer, and edit-mode geometry loading. No interactions yet.

- [ ] **Step 1: Create the component**

Create `assets/frontend/pages/AreaEditorPage.vue`:

```vue
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, markRaw } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Select from "primevue/select";
import { Map as OLMap, View } from "ol";
import { fromLonLat } from "ol/proj";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import { GeoJSON } from "ol/format";
import { Draw, Modify, Select as OLSelect, Snap } from "ol/interaction";
import { Style, Stroke, Fill } from "ol/style";
import Feature from "ol/Feature";
import type { Polygon } from "ol/geom";
import { MultiPolygon as OLMultiPolygon } from "ol/geom";
import { useBaseLayer, makeBaseLayer, BASE_LAYER_OPTIONS } from "../composables/useBaseLayer";
import { getCsrf } from "../utils/csrf";
import "ol/ol.css";

type ActiveMode = "draw" | "edit" | "delete";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const toast = useToast();
const confirm = useConfirm();

const areaId = computed((): number | null => {
    const id = route.params.id;
    return id ? parseInt(id as string, 10) : null;
});
const isEditMode = computed(() => areaId.value !== null);

const areaName = ref("");
const polygonCount = ref(0);
const activeMode = ref<ActiveMode>("draw");
const isDirty = ref(false);
const saving = ref(false);
const loading = ref(false);
const errorMessage = ref<string | null>(null);
const pendingDeleteFeature = ref<Feature | null>(null);

const { selectedBaseLayerId, attachToMap } = useBaseLayer();
const mapEl = ref<HTMLElement | null>(null);
let olMap: OLMap | null = null;

const vectorSource = new VectorSource();
const vectorLayer = markRaw(
    new VectorLayer({
        source: vectorSource,
        style: new Style({
            stroke: new Stroke({ color: "#0b6efd", width: 3 }),
            fill: new Fill({ color: "rgba(11, 110, 253, 0.1)" }),
        }),
    })
);

let drawInteraction: Draw | null = null;
let modifyInteraction: Modify | null = null;
let selectInteraction: OLSelect | null = null;
let snapInteraction: Snap | null = null;

function clearInteractions(): void {
    if (!olMap) return;
    for (const i of [drawInteraction, modifyInteraction, selectInteraction, snapInteraction]) {
        if (i) olMap.removeInteraction(i);
    }
    drawInteraction = null;
    modifyInteraction = null;
    selectInteraction = null;
    snapInteraction = null;
}

function activateDrawMode(): void {
    clearInteractions();
    if (!olMap) return;
    drawInteraction = markRaw(new Draw({ source: vectorSource, type: "Polygon" }));
    drawInteraction.on("drawend", () => {
        polygonCount.value++;
        isDirty.value = true;
    });
    snapInteraction = markRaw(new Snap({ source: vectorSource }));
    olMap.addInteraction(drawInteraction);
    olMap.addInteraction(snapInteraction);
    activeMode.value = "draw";
    pendingDeleteFeature.value = null;
}

function activateEditMode(): void {
    clearInteractions();
    if (!olMap) return;
    modifyInteraction = markRaw(new Modify({ source: vectorSource }));
    modifyInteraction.on("modifyend", () => { isDirty.value = true; });
    snapInteraction = markRaw(new Snap({ source: vectorSource }));
    olMap.addInteraction(modifyInteraction);
    olMap.addInteraction(snapInteraction);
    activeMode.value = "edit";
    pendingDeleteFeature.value = null;
}

function activateDeleteMode(): void {
    clearInteractions();
    if (!olMap) return;
    selectInteraction = markRaw(new OLSelect());
    selectInteraction.on("select", (e) => {
        if (e.selected.length > 0) {
            pendingDeleteFeature.value = e.selected[0];
        }
    });
    olMap.addInteraction(selectInteraction);
    activeMode.value = "delete";
}

function confirmDeletePolygon(): void {
    if (!pendingDeleteFeature.value) return;
    vectorSource.removeFeature(pendingDeleteFeature.value);
    polygonCount.value--;
    isDirty.value = true;
    activateEditMode();
}

function cancelDeletePolygon(): void {
    selectInteraction?.getFeatures().clear();
    pendingDeleteFeature.value = null;
    activateEditMode();
}

const canSave = computed(
    () => areaName.value.trim() !== "" && polygonCount.value > 0 && !saving.value
);
const canDeletePolygon = computed(() => polygonCount.value > 1);

async function save(): Promise<void> {
    if (!canSave.value) return;
    saving.value = true;
    errorMessage.value = null;

    const geojson = new GeoJSON().writeFeaturesObject(
        vectorSource.getFeatures(),
        { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857" }
    );

    const url = isEditMode.value
        ? `/api/v2/areas/${areaId.value}/`
        : "/api/v2/areas/from-drawing/";
    const method = isEditMode.value ? "PATCH" : "POST";

    const resp = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
        body: JSON.stringify({ name: areaName.value, geojson }),
    });

    saving.value = false;

    if (resp.ok) {
        toast.add({ severity: "success", summary: t("message.areaSaved"), life: 3000 });
        await router.push("/my-custom-areas");
    } else {
        const data = await resp.json();
        errorMessage.value = data.detail ?? t("message.unexpectedError");
    }
}

function promptDeleteArea(): void {
    confirm.require({
        message: t("message.confirmDeleteArea"),
        header: t("message.confirmDeleteAreaHeader"),
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: doDeleteArea,
    });
}

async function doDeleteArea(): Promise<void> {
    const resp = await fetch(`/api/v2/areas/${areaId.value}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrf() },
    });
    if (resp.status === 204) {
        toast.add({ severity: "success", summary: t("message.areaDeleted"), life: 3000 });
        await router.push("/my-custom-areas");
    } else if (resp.status === 409) {
        const data = await resp.json();
        errorMessage.value = data.detail;
    }
}

onMounted(async () => {
    olMap = markRaw(
        new OLMap({
            target: mapEl.value!,
            layers: [markRaw(makeBaseLayer("osmHot")), vectorLayer],
            view: new View({ zoom: 2, center: fromLonLat([0, 20]) }),
        })
    );
    attachToMap(olMap);

    if (isEditMode.value && areaId.value !== null) {
        loading.value = true;
        const resp = await fetch(`/api/v2/areas/${areaId.value}/geojson/`);
        if (resp.ok) {
            const geojson = await resp.json();

            // The Django GeoJSON serializer includes model fields as properties.
            // Extract the area name from the first feature's properties.
            const name: string | undefined = geojson.features?.[0]?.properties?.name;
            if (name) areaName.value = name;

            // Split any MultiPolygon feature into individual Polygon features
            // so each polygon can be independently selected and deleted.
            const rawFeatures = new GeoJSON().readFeatures(geojson, {
                dataProjection: "EPSG:4326",
                featureProjection: "EPSG:3857",
            });
            const splitFeatures: Feature[] = [];
            for (const feat of rawFeatures) {
                const geom = feat.getGeometry();
                if (geom?.getType() === "MultiPolygon") {
                    const mp = geom as OLMultiPolygon;
                    for (const poly of mp.getPolygons()) {
                        splitFeatures.push(new Feature<Polygon>({ geometry: poly }));
                    }
                } else {
                    splitFeatures.push(feat);
                }
            }
            vectorSource.addFeatures(splitFeatures);
            polygonCount.value = splitFeatures.length;

            const extent = vectorSource.getExtent();
            if (extent && extent.every(isFinite)) {
                olMap.getView().fit(extent, { padding: [20, 20, 20, 20] });
            }
        }
        loading.value = false;
        activateEditMode();
    } else {
        activateDrawMode();
    }
});

onUnmounted(() => {
    olMap?.setTarget(undefined);
    olMap = null;
});
</script>

<template>
    <div class="editor-page">
        <!-- Map area -->
        <div ref="mapEl" class="editor-map">
            <!-- Base layer control - floating top-right, same style as BaseMap.vue -->
            <div class="map-float-controls">
                <div class="float-control-row">
                    <span class="float-control-label">{{ t("message.baseLayer") }}</span>
                    <Select
                        v-model="selectedBaseLayerId"
                        :options="BASE_LAYER_OPTIONS"
                        option-label="label"
                        option-value="id"
                        size="small"
                        class="base-layer-select"
                    />
                </div>
            </div>
            <!-- Hint overlay shown in create mode before any polygon is drawn -->
            <div v-if="!isEditMode && polygonCount === 0 && !loading" class="draw-hint">
                {{ t("message.clickToStartDrawing") }}
            </div>
        </div>

        <!-- Right sidebar -->
        <div class="editor-sidebar">
            <!-- Area name input -->
            <div class="sidebar-section">
                <label class="sidebar-label" for="editor-area-name">
                    {{ t("message.areaName") }}
                </label>
                <InputText
                    id="editor-area-name"
                    v-model="areaName"
                    class="w-full"
                    :placeholder="t('message.areaName') + '...'"
                />
            </div>

            <div class="sidebar-divider" />

            <!-- Tool buttons -->
            <div class="sidebar-section">
                <div class="sidebar-label">{{ t("message.drawingTool") }}</div>

                <!-- Normal tool list -->
                <div v-if="!(activeMode === 'delete' && pendingDeleteFeature)" class="tool-buttons">
                    <Button
                        :label="t('message.drawPolygon')"
                        icon="pi pi-pencil"
                        :outlined="activeMode !== 'draw'"
                        size="small"
                        fluid
                        @click="activateDrawMode"
                    />
                    <Button
                        :label="t('message.editVertices')"
                        icon="pi pi-arrows-alt"
                        :outlined="activeMode !== 'edit'"
                        size="small"
                        fluid
                        @click="activateEditMode"
                    />
                    <Button
                        :label="t('message.deletePolygon')"
                        icon="pi pi-trash"
                        :outlined="activeMode !== 'delete'"
                        :disabled="!canDeletePolygon"
                        size="small"
                        fluid
                        @click="activateDeleteMode"
                    />
                </div>

                <!-- Delete polygon confirmation (replaces tool list) -->
                <div v-else class="delete-confirm">
                    <p class="delete-confirm-label">{{ t("message.confirmDeletePolygon") }}</p>
                    <Button
                        :label="t('message.yesImSure')"
                        severity="danger"
                        size="small"
                        fluid
                        @click="confirmDeletePolygon"
                    />
                    <Button
                        :label="t('message.cancel')"
                        severity="secondary"
                        size="small"
                        fluid
                        @click="cancelDeletePolygon"
                    />
                </div>

                <small class="sidebar-hint">
                    {{ t("message.polygonCount", { count: polygonCount }) }}
                </small>
            </div>

            <!-- Spacer pushes save/delete to bottom -->
            <div class="sidebar-spacer" />

            <!-- Unsaved changes indicator (edit mode only) -->
            <div v-if="isEditMode && isDirty" class="unsaved-indicator">
                {{ t("message.unsavedChanges") }}
            </div>

            <!-- API error message -->
            <Message v-if="errorMessage" severity="error" class="mb-2" :closable="false">
                {{ errorMessage }}
            </Message>

            <!-- Save / Cancel -->
            <div class="sidebar-section">
                <Button
                    :label="t('message.save')"
                    :disabled="!canSave"
                    :loading="saving"
                    fluid
                    @click="save"
                />
                <Button
                    :label="t('message.cancel')"
                    severity="secondary"
                    class="mt-2"
                    fluid
                    @click="router.push('/my-custom-areas')"
                />
            </div>

            <!-- Delete area button (edit mode only) -->
            <template v-if="isEditMode">
                <div class="sidebar-divider" />
                <div class="sidebar-section">
                    <Button
                        :label="t('message.deleteAreaButton')"
                        icon="pi pi-trash"
                        severity="danger"
                        outlined
                        fluid
                        @click="promptDeleteArea"
                    />
                </div>
            </template>
        </div>
    </div>
</template>

<style scoped>
.editor-page {
    display: flex;
    /* Subtract the app header height. Adjust if the app shell uses a different value. */
    height: calc(100vh - 60px);
    overflow: hidden;
}

.editor-map {
    flex: 1;
    position: relative;
}

/* Replicates the floating controls style from BaseMap.vue */
.map-float-controls {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    z-index: 100;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(3px);
    border-radius: 6px;
    padding: 0.5rem 0.65rem;
    box-shadow: 0 1px 5px rgba(0, 0, 0, 0.22);
    min-width: 155px;
    pointer-events: auto;
}

.float-control-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.float-control-label {
    font-size: 0.78rem;
    white-space: nowrap;
    color: var(--p-text-color);
    flex-shrink: 0;
}

.base-layer-select {
    flex: 1;
    min-width: 0;
}

.draw-hint {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(4px);
    border-radius: 8px;
    padding: 0.75rem 1.25rem;
    font-size: 0.95rem;
    color: var(--p-text-color);
    pointer-events: none;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.editor-sidebar {
    width: 220px;
    flex-shrink: 0;
    background: var(--p-surface-card);
    border-left: 1px solid var(--p-surface-border);
    display: flex;
    flex-direction: column;
    padding: 1rem 0.875rem;
    overflow-y: auto;
}

.sidebar-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}

.sidebar-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--p-text-muted-color);
    font-weight: 600;
}

.sidebar-hint {
    font-size: 0.75rem;
    color: var(--p-text-muted-color);
}

.sidebar-divider {
    border-top: 1px solid var(--p-surface-border);
    margin: 0.5rem 0;
}

.sidebar-spacer {
    flex: 1;
}

.tool-buttons {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.unsaved-indicator {
    font-size: 0.8rem;
    color: var(--p-orange-400);
    margin-bottom: 0.5rem;
}

.delete-confirm {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.delete-confirm-label {
    margin: 0;
    font-size: 0.875rem;
}
</style>
```

- [ ] **Step 2: Check the page loads in the browser**

```bash
npm run dev
```

Navigate to `/my-custom-areas/new` while logged in. You should see a full-page layout: map on the left, sidebar on the right with name input and tool buttons. The "Click on the map to start drawing" hint should be visible.

Navigate to `/my-custom-areas/<existing-id>/edit`. The area name should be pre-filled and the existing polygons should appear on the map.

- [ ] **Step 3: Commit**

```bash
git add assets/frontend/pages/AreaEditorPage.vue
git commit -m "feat: add AreaEditorPage with map, geometry loading, and editor interactions"
```

---

## Task 10: Playwright E2E tests for the editor

**Files:**
- Modify: `dashboard/tests/playwright/test_areas.py`

- [ ] **Step 1: Add editor tests**

Append to `dashboard/tests/playwright/test_areas.py`:

```python
# ---------------------------------------------------------------------------
# /my-custom-areas/new - editor create mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_editor_create_mode_loads(page: Page, live_server):
    """Create-mode editor page renders with correct elements."""
    User = get_user_model()
    User.objects.create_user(username="e1", password="pass", email="e1@t.com")

    _login(page, live_server.url, "e1", "pass")
    page.goto(live_server.url + "/my-custom-areas/new")
    page.wait_for_load_state("networkidle")

    expect(page.locator("#editor-area-name")).to_be_visible()
    expect(page.get_by_role("button", name="Draw polygon")).to_be_visible()
    expect(page.get_by_role("button", name="Edit vertices")).to_be_visible()
    expect(page.get_by_role("button", name="Delete polygon")).to_be_visible()
    expect(page.get_by_role("button", name="Save")).to_be_visible()
    expect(page.get_by_role("button", name="Cancel")).to_be_visible()
    # Save is disabled - no name or polygon yet
    expect(page.get_by_role("button", name="Save")).to_be_disabled()
    # "Delete area" button must NOT appear in create mode
    expect(page.get_by_role("button", name="Delete area")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_editor_create_mode_requires_login(page: Page, live_server):
    """Anonymous user is redirected away from the create editor."""
    page.goto(live_server.url + "/my-custom-areas/new")
    page.wait_for_load_state("networkidle")
    expect(page).not_to_have_url(live_server.url + "/my-custom-areas/new")


# ---------------------------------------------------------------------------
# /my-custom-areas/:id/edit - editor edit mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_editor_edit_mode_prefills_name(page: Page, live_server):
    """Edit-mode editor pre-fills the area name input."""
    User = get_user_model()
    user = User.objects.create_user(username="e2", password="pass", email="e2@t.com")
    area = _make_area(user, "Prefilled area")

    _login(page, live_server.url, "e2", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    expect(page.locator("#editor-area-name")).to_have_value("Prefilled area")
    expect(page.get_by_role("button", name="Delete area")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_editor_edit_mode_rename_and_save(page: Page, live_server):
    """Renaming an area via the editor persists to the database."""
    User = get_user_model()
    user = User.objects.create_user(username="e3", password="pass", email="e3@t.com")
    area = _make_area(user, "Old name")

    _login(page, live_server.url, "e3", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    page.locator("#editor-area-name").fill("New name")
    page.get_by_role("button", name="Save").click()
    page.wait_for_load_state("networkidle")

    # Should redirect back to the list page
    expect(page).to_have_url(live_server.url + "/my-custom-areas")

    area.refresh_from_db()
    assert area.name == "New name"


@pytest.mark.django_db(transaction=True)
def test_editor_delete_area_button(page: Page, live_server):
    """Delete area button in the editor removes the area and redirects to the list."""
    User = get_user_model()
    user = User.objects.create_user(username="e4", password="pass", email="e4@t.com")
    area = _make_area(user, "Area to delete from editor")

    _login(page, live_server.url, "e4", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Delete area").click()
    # PrimeVue ConfirmDialog - click the accept button
    page.get_by_role("button", name="Yes, I'm sure").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/my-custom-areas")
    assert not Area.objects.filter(pk=area.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_editor_cancel_returns_to_list(page: Page, live_server):
    """Clicking Cancel in the editor navigates back to the area list."""
    User = get_user_model()
    user = User.objects.create_user(username="e5", password="pass", email="e5@t.com")
    area = _make_area(user, "Stay intact")

    _login(page, live_server.url, "e5", "pass")
    page.goto(live_server.url + f"/my-custom-areas/{area.pk}/edit")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Cancel").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(live_server.url + "/my-custom-areas")
```

- [ ] **Step 2: Run the Playwright tests**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/playwright/test_areas.py -v
```

Expected: All new tests PASS. The existing tests should also still pass.

- [ ] **Step 3: Run the full test suite**

```
DJANGO_SETTINGS_MODULE=djangoproject.local_settings python -m pytest dashboard/tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add dashboard/tests/playwright/test_areas.py
git commit -m "test: add Playwright E2E tests for the area editor page"
```

---

## Self-review checklist

- [x] **Spec coverage:** `geojson_to_multipolygon` covered in Task 1; `POST /areas/from-drawing/` in Task 3; `PATCH /areas/{id}/` in Task 4; `useBaseLayer` composable in Task 6; routes in Task 7; `UserAreasPage`/`AreaCard` buttons in Task 8; `AreaEditorPage` with all interactions in Task 9; Playwright tests in Task 10.
- [x] **No placeholders:** All tasks contain complete code.
- [x] **Type consistency:** `activateDrawMode`, `activateEditMode`, `activateDeleteMode`, `confirmDeletePolygon`, `cancelDeletePolygon` all defined before use. `makeBaseLayer` and `BASE_LAYER_OPTIONS` exported from `useBaseLayer.ts` and imported by name in both `BaseMap.vue` and `AreaEditorPage.vue`. `geojson_to_multipolygon` added to `geo_utils.py` and imported in `api_v2.py`. `AreaFromDrawingIn` and `AreaPatchIn` defined in `api_v2_schemas.py` and imported in `api_v2.py`.
