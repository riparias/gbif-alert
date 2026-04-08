# Custom Areas Map Editor - Design Spec

**Date:** 2026-04-08
**Scope:** Stage 1 - map-based polygon editor for /my-custom-areas. Stage 2 (enhanced upload, multi-format) is out of scope.

---

## Problem

The current `/my-custom-areas` page only supports uploading a GeoPackage file (single layer, polygon/multipolygon only) to create an area. There is no way to draw a new area from scratch or edit the geometry of an existing one.

---

## Routes

Two new Vue Router routes, both resolving to `AreaEditorPage.vue`:

| Path | Mode |
|---|---|
| `/my-custom-areas/new` | Create - blank editor, starts in Draw mode |
| `/my-custom-areas/:id/edit` | Edit - loads existing geometry, starts in Edit vertices mode |

`UserAreasPage.vue` gains:
- A "New area" button that navigates to `/my-custom-areas/new`
- An "Edit" button on each `AreaCard` that navigates to `/my-custom-areas/:id/edit`

---

## Frontend Architecture

### `useBaseLayer.ts` (new composable)

Extracted from `BaseMap.vue`. Contains:
- `BASE_LAYER_OPTIONS` constant (OSM HOT, Stamen Toner, ESRI World Imagery)
- `makeBaseLayer(id)` factory function
- `selectedBaseLayerId` ref
- `attachToMap(olMap: OLMap)` - sets up the watch that swaps the base layer when `selectedBaseLayerId` changes; called after the map is created in `onMounted`

`BaseMap.vue` is refactored to use this composable - no breaking changes to its external API (same props, same `getOlMap()` expose, same template). `AreaEditorPage.vue` also uses it independently.

### `AreaEditorPage.vue` (new page component)

Creates its own OL map directly (not via `<BaseMap>`) so it can attach editing interactions without going through `getOlMap()`. Uses `useBaseLayer()` for background switching.

**Internal state:**
- `VectorSource` containing individual `Feature<Polygon>` objects - one per polygon in the area
- `activeMode`: `"draw" | "edit" | "delete"`
- `areaName`: string (empty in create mode, pre-filled in edit mode)
- `isDirty`: boolean (drives the "Unsaved changes" indicator)

**OL interactions, swapped by `activeMode`:**
- `Draw` (Polygon) - on `drawend`, adds the new feature to the vector source
- `Modify` + `Select` - vertex editing of existing features
- `Select` (click) + confirmation step - removes selected feature from source; disabled when only one polygon remains
- `Snap` - always active alongside whichever interaction is current; improves vertex alignment at no UX cost

**Layout:** Full-page, map fills the left side, 200px right sidebar.

### Right sidebar contents

| Element | Create mode | Edit mode |
|---|---|---|
| Area name | Empty input, placeholder "Area name..." | Pre-filled from API |
| Tool buttons | Draw polygon (active), Edit vertices, Delete polygon | Edit vertices (active), Draw polygon, Delete polygon |
| Polygon count | "0 polygons in this area" | "N polygons in this area" |
| Unsaved indicator | Hidden | Shown when dirty |
| Save button | Disabled until name non-empty AND >= 1 polygon | Enabled |
| Cancel button | Navigates back to list | Navigates back to list |
| Delete area button | Hidden | Visible (red, asks for confirmation) |

**Tool labels used consistently:** "Draw polygon", "Edit vertices", "Delete polygon", "Delete area".

**Create mode hint:** Until the first polygon is drawn, a map overlay shows "Click on the map to start drawing".

**Delete polygon flow:** Clicking a polygon highlights it; sidebar temporarily shows "Delete this polygon? [Confirm] [Cancel]" replacing the tool list. Cannot delete the last polygon (Save requires at least one).

**Delete area flow:** Uses existing `DELETE /api/v2/areas/{area_id}/`. If the API returns 409 (area has linked alerts), shows the error; does not navigate away.

---

## API Changes

### New: `POST /api/v2/areas/from-drawing/` (auth required)

Creates a new user area from drawn GeoJSON geometry.

```
Request body:
  name: str
  geojson: dict  -- GeoJSON FeatureCollection, EPSG:4326, Polygon/MultiPolygon features

Response:
  201: AreaOut
  422: AreaCreateError  -- reuses existing error schema
```

Backend logic: reproject features to SRID 3857, merge all into a single `MultiPolygon`, create `Area(owner=request.user, name=name, mpoly=merged)`.

### New: `PATCH /api/v2/areas/{area_id}/` (auth required)

Updates name and/or geometry of an existing user-owned area. Both fields are optional. `null` means "leave unchanged" - there is no way to clear the geometry via this endpoint (an area must always have geometry).

```
Request body:
  name: str | None
  geojson: dict | None  -- same format as above

Response:
  200: AreaOut
  403: area not owned by requesting user
  404: area not found
```

### Unchanged endpoints

- `GET /api/v2/areas/` - list areas
- `GET /api/v2/areas/{area_id}/geojson/` - fetch geometry for editor (edit mode loads from this)
- `POST /api/v2/areas/` - geopackage upload (unchanged, Stage 2 will improve this)
- `DELETE /api/v2/areas/{area_id}/` - used by the "Delete area" button as-is

---

## Data flow: save on create

1. User draws polygons -> each stored as `Feature<Polygon>` in `VectorSource`
2. User types area name
3. User clicks Save
4. Frontend serialises `VectorSource` features to a GeoJSON FeatureCollection (EPSG:4326 via OL's `GeoJSON` format class)
5. `POST /api/v2/areas/from-drawing/` with `{ name, geojson }`
6. On 201: navigate to `/my-custom-areas`, show success toast
7. On 422: show error message in sidebar

## Data flow: save on edit

1. Editor loads: `GET /api/v2/areas/{id}/geojson/` -> parse FeatureCollection -> add individual polygon features to `VectorSource`
2. User modifies geometry and/or name
3. User clicks Save
4. `PATCH /api/v2/areas/{id}/` with changed fields
5. On 200: navigate to `/my-custom-areas`, show success toast
6. On error: show message in sidebar

---

## Out of scope (Stage 2)

- Multi-format upload (GeoJSON, KML, Shapefile, etc.)
- Importing multiple features at once as separate areas
- Undo/redo in the editor
