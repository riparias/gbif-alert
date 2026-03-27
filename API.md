# API Reference

This document describes all HTTP endpoints exposed by the application.

---

## Table of Contents

1. [Common Filtering Parameters](#common-filtering-parameters)
2. [Public API (`/api/`)](#public-api)
   - [Species list](#species-list)
   - [Species per polygon](#species-per-polygon)
   - [Filtered observations - count](#filtered-observations---count)
   - [Filtered observations - paginated data](#filtered-observations---paginated-data)
3. [WFS API (`/api/wfs/`)](#wfs-api)
   - [Observations WFS](#observations-wfs)
4. [Internal API (`/internal-api/`)](#internal-api)
   - [Areas list](#areas-list)
   - [Area GeoJSON](#area-geojson)
   - [Datasets list](#datasets-list)
   - [Basis of record list](#basis-of-record-list)
   - [Data imports list](#data-imports-list)
   - [Filtered observations - monthly histogram](#filtered-observations---monthly-histogram)
   - [Filtered observations - mark as seen](#filtered-observations---mark-as-seen)
   - [Available alert intervals](#available-alert-intervals)
   - [Suggest alert name](#suggest-alert-name)
   - [Alert - retrieve](#alert---retrieve)
   - [Alert - create / update](#alert---create--update)
   - [Alert as dashboard filters](#alert-as-dashboard-filters)
5. [Maps API (`/internal-api/maps/`)](#maps-api)
   - [Min/max observations per hexagon](#minmax-observations-per-hexagon)
   - [MVT tiles - individual observations](#mvt-tiles---individual-observations)
   - [MVT tiles - hexagon-grid aggregated](#mvt-tiles---hexagon-grid-aggregated)
6. [Actions (`/actions/`)](#actions)
   - [Delete alert](#delete-alert)
   - [Mark observation as unseen](#mark-observation-as-unseen)
   - [Delete own account](#delete-own-account)
   - [Delete area](#delete-area)

---

## Common Filtering Parameters

Many endpoints accept the same set of optional GET parameters to filter observations. These are referred to as **"observation filters"** throughout this document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `speciesIds[]` | integer (repeatable) | Restrict to specific species |
| `datasetsIds[]` | integer (repeatable) | Restrict to specific datasets |
| `basisOfRecordIds[]` | integer (repeatable) | Restrict to specific basis-of-record values |
| `areaIds[]` | integer (repeatable) | Restrict to observations within specified areas |
| `initialDataImportIds[]` | integer (repeatable) | Restrict to specific data import batches |
| `startDate` | `YYYY-MM-DD` | Earliest observation date (inclusive) |
| `endDate` | `YYYY-MM-DD` | Latest observation date (inclusive) |
| `status` | `seen` or `unseen` | Filter by seen/unseen status - **requires authentication**; ignored for anonymous requests |
| `verifiedFilter` | `all`, `verified`, or `unverified` | Filter by verification status (default: `all`) |

---

## Public API

Base path: `/api/`

No authentication required for any of these endpoints.

---

### Species list

```
GET /api/species
```

Returns all species in the system.

**Response** `200 OK` - JSON array

```json
[
  {
    "id": 1,
    "scientificName": "Vespa velutina",
    "vernacularName": "Asian hornet",
    "gbifTaxonKey": 1311477,
    "tags": ["invasive", "bee threat"]
  }
]
```

---

### Species per polygon

```
GET /api/species-per-polygon
```

Returns the species observed within a given polygon, along with observation counts.

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `p` | Yes | URL-encoded WKT polygon string (EPSG:4326) |

**Response** `200 OK` - JSON array

```json
[
  {
    "id": 1,
    "scientificName": "Vespa velutina",
    "vernacularName": "Asian hornet",
    "gbifTaxonKey": 1311477,
    "groupCode": "insects",
    "observationCountInPolygon": 42
  }
]
```

---

### Filtered observations - count

```
GET /api/filtered-observations/counter
```

Returns the number of observations matching the given filters.

**Query parameters** - [observation filters](#common-filtering-parameters)

**Response** `200 OK`

```json
{ "count": 1234 }
```

---

### Filtered observations - paginated data

```
GET /api/filtered-observations/data_page
```

Returns a paginated list of observations matching the given filters.

**Query parameters**

| Parameter | Description |
|-----------|-------------|
| [observation filters](#common-filtering-parameters) | See above |
| `order` | Field to order by (passed to `QuerySet.order_by`), e.g. `pk`, `-date`, `species__name` |
| `mode` | `normal` (default) or `short` - controls response detail level |
| `limit` | Items per page (default: 50) |
| `page_number` | Page number to retrieve. If negative or beyond the last page, the last page is returned |

**Response** `200 OK` (normal mode)

```json
{
  "results": [
    {
      "id": 99,
      "stableId": "abc123",
      "gbifId": "4099394870",
      "lat": 51.05,
      "lon": 3.72,
      "scientificName": "Vespa velutina",
      "vernacularName": "Asian hornet",
      "displayNameHtml": "<em>Vespa velutina</em> - Asian hornet",
      "datasetName": "iNaturalist Research-grade Observations",
      "date": "2023-07-14",
      "seenByCurrentUser": false
    }
  ],
  "pageNumber": 1,
  "firstPage": 1,
  "lastPage": 25,
  "totalResultsCount": 1234
}
```

`seenByCurrentUser` is only present for authenticated users.

**Response** `200 OK` (short mode)

```json
{
  "results": [
    {
      "id": 99,
      "lat": 51.05,
      "lon": 3.72,
      "scientificName": "Vespa velutina",
      "speciesId": 1,
      "date": "2023-07-14"
    }
  ],
  "pageNumber": 1,
  "firstPage": 1,
  "lastPage": 25,
  "totalResultsCount": 1234
}
```

---

## WFS API

Base path: `/api/wfs/`

No authentication required.

---

### Observations WFS

```
GET /api/wfs/observations
```

OGC Web Feature Service endpoint for observations, implemented via `django-gisserver`.

**Supported WFS operations**

- `GetCapabilities` - returns the service description
- `DescribeFeatureType` - returns the schema of the `Observation` feature type
- `GetFeature` - returns features as GeoJSON, GML, or other WFS output formats

Example request:

```
GET /api/wfs/observations?service=WFS&version=2.0.0&request=GetFeature&typeName=dashboard_Observation
```

**Exposed feature properties**

| Property | Type | Description |
|----------|------|-------------|
| `location` | Point geometry | Observation location |
| `gbif_id` | string | GBIF occurrence ID |
| `stable_id` | string | Internal stable identifier |
| `species_id` | integer | Internal species ID |
| `species_gbif_key` | string | GBIF taxon key |
| `species_scientific_name` | string | Scientific name |
| `species_vernacular_name_nl` | string | Dutch common name |
| `species_vernacular_name_en` | string | English common name |
| `species_vernacular_name_fr` | string | French common name |
| `dataset_name` | string | Source dataset name |
| `dataset_gbif_key` | string | GBIF dataset key |
| `observation_date` | date | Date of observation |
| `individual_count` | integer | Number of individuals recorded |
| `locality` | string | Textual locality description |
| `municipality` | string | Municipality |
| `basis_of_record` | string | Darwin Core basis of record |
| `recorded_by` | string | Observer name(s) |
| `coordinate_uncertainty_in_meters` | integer | Coordinate uncertainty |
| `references` | string | External reference URL |
| `verified` | boolean | Whether the observation has been verified |

---

## Internal API

Base path: `/internal-api/`

These endpoints are intended for the frontend. Some require authentication.

---

### Areas list

```
GET /internal-api/areas
```

Returns areas available to the current user. Anonymous users only see public areas; authenticated users also see their own private areas.

**Response** `200 OK` - JSON array

```json
[
  {
    "id": 5,
    "name": "Ghent city center",
    "isUserSpecific": true,
    "tags": ["city"]
  }
]
```

---

### Area GeoJSON

```
GET /internal-api/area/<id>
```

Returns the geometry of a single area as a GeoJSON FeatureCollection.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `id` | Area ID |

**Response** `200 OK` - GeoJSON FeatureCollection

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "MultiPolygon", "coordinates": [...] },
      "properties": { "pk": 5, "name": "Ghent city center" }
    }
  ]
}
```

**Errors**

- `403 Forbidden` - area is not accessible to the current user

---

### Datasets list

```
GET /internal-api/datasets
```

Returns all datasets.

**Response** `200 OK` - JSON array

```json
[
  {
    "id": 3,
    "gbifKey": "50c9509d-22c7-4a22-a47d-8c48425ef4a7",
    "name": "iNaturalist Research-grade Observations"
  }
]
```

---

### Basis of record list

```
GET /internal-api/basis-of-record
```

Returns all basis-of-record values.

**Response** `200 OK` - JSON array

```json
[
  { "id": 1, "name": "HUMAN_OBSERVATION" }
]
```

---

### Data imports list

```
GET /internal-api/data-imports
```

Returns all data import batches.

**Response** `200 OK` - JSON array

```json
[
  {
    "id": 7,
    "name": "Data import #7",
    "startTimestamp": "2023-11-15T08:32:00Z"
  }
]
```

---

### Filtered observations - monthly histogram

```
GET /internal-api/filtered-observations/monthly_histogram
```

Returns per-month observation counts for the given filters.

**Query parameters** - [observation filters](#common-filtering-parameters)

**Response** `200 OK` - JSON array, ordered chronologically

```json
[
  { "year": 2023, "month": 7, "count": 84 },
  { "year": 2023, "month": 8, "count": 112 }
]
```

---

### Filtered observations - mark as seen

```
POST /internal-api/filtered-observations/mark_as_seen
```

Queues a background job to mark all matching observations as seen by the authenticated user.

**Authentication** - Required

**Query parameters** - [observation filters](#common-filtering-parameters)

**Response** `200 OK`

```json
{ "queued": true }
```

---

### Available alert intervals

```
GET /internal-api/available-alert-intervals
```

Returns the notification frequency options that can be set on an alert.

**Response** `200 OK` - JSON array

```json
[
  { "id": "daily",  "label": "Daily"  },
  { "id": "weekly", "label": "Weekly" },
  { "id": "never",  "label": "Never"  }
]
```

---

### Suggest alert name

```
GET /internal-api/suggest-alert-name
```

Returns a suggested name for a new alert based on the user's existing alerts (e.g. `My alert #3`).

**Authentication** - Required

**Response** `200 OK`

```json
{ "name": "My alert #3" }
```

---

### Alert - retrieve

```
GET /internal-api/alert?alert_id=<id>
```

Returns the configuration of an existing alert owned by the authenticated user.

**Authentication** - Required

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `alert_id` | Yes | Alert ID |

**Response** `200 OK`

```json
{
  "id": 12,
  "name": "Invasive species in Ghent",
  "speciesIds": [1, 4],
  "datasetIds": [3],
  "basisOfRecordIds": [],
  "areaIds": [5],
  "emailNotificationsFrequency": "weekly",
  "verifiedFilter": "all"
}
```

---

### Alert - create / update

```
POST /internal-api/alert
```

Creates a new alert (when `id` is `null`) or updates an existing one.

**Authentication** - Required

**Request body** - JSON

```json
{
  "id": null,
  "name": "Invasive species in Ghent",
  "speciesIds": [1, 4],
  "areaIds": [5],
  "datasetIds": [3],
  "basisOfRecordIds": [],
  "emailNotificationsFrequency": "weekly",
  "verifiedFilter": "all"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | `null` to create, integer to update |
| `name` | Yes | Non-empty |
| `speciesIds` | Yes | At least one species required |
| `areaIds` | Yes | |
| `datasetIds` | Yes | |
| `basisOfRecordIds` | No | Defaults to `[]` |
| `emailNotificationsFrequency` | Yes | One of the available interval IDs |
| `verifiedFilter` | No | `all` (default), `verified`, or `unverified` |

**Response** `200 OK`

```json
{
  "alertId": 12,
  "success": true,
  "errors": {}
}
```

On validation failure, `success` is `false` and `errors` maps field names to lists of error messages.

**Errors**

- `403 Forbidden` - attempting to update an alert not owned by the current user

---

### Alert as dashboard filters

```
GET /internal-api/alert/as-filters?alert_id=<id>
```

Returns an alert's configuration translated into dashboard filter form, useful for pre-populating the observation filter UI from an alert.

**Authentication** - Required

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `alert_id` | Yes | Alert ID |

**Response** `200 OK`

```json
{
  "speciesIds": [1, 4],
  "datasetsIds": [3],
  "basisOfRecordIds": [],
  "areaIds": [5],
  "startDate": null,
  "endDate": null,
  "status": "unseen",
  "verifiedFilter": "all"
}
```

---

## Maps API

Base path: `/internal-api/maps/`

All endpoints serve data for map visualisation. No authentication required.

---

### Min/max observations per hexagon

```
GET /internal-api/maps/min-max-per-hexagon
```

Returns the minimum and maximum observation counts across all hexagons at the given zoom level, for the current filters. Used to calibrate the colour scale of the hexagon layer.

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `zoom` | Yes | Map zoom level (determines hexagon size) |
| [observation filters](#common-filtering-parameters) | No | See above |

**Response** `200 OK`

```json
{ "min": 1, "max": 847 }
```

---

### MVT tiles - individual observations

```
GET /internal-api/maps/tiles/observations/<zoom>/<x>/<y>.mvt
```

Returns a Mapbox Vector Tile containing individual observation points.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `zoom` | Zoom level |
| `x` | Tile column |
| `y` | Tile row |

**Query parameters** - [observation filters](#common-filtering-parameters)

**Response** `200 OK` - `application/vnd.mapbox-vector-tile` (binary)

Each feature in the tile exposes:

| Property | Type | Description |
|----------|------|-------------|
| `gbif_id` | string | GBIF occurrence ID |
| `stable_id` | string | Internal stable identifier |
| `scientific_name` | string | Scientific name |
| `location` | Point | Observation location |

---

### MVT tiles - hexagon-grid aggregated

```
GET /internal-api/maps/tiles/observations/hexagon-grid-aggregated/<zoom>/<x>/<y>.mvt
```

Returns a Mapbox Vector Tile containing aggregated hexagon grid cells. Hexagon size is determined by zoom level (configured in `settings.ZOOM_TO_HEX_SIZE`). The hexagons are pre-computed into PostgreSQL materialized views for performance.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `zoom` | Zoom level |
| `x` | Tile column |
| `y` | Tile row |

**Query parameters** - [observation filters](#common-filtering-parameters)

**Response** `200 OK` - `application/vnd.mapbox-vector-tile` (binary)

Each feature in the tile exposes:

| Property | Type | Description |
|----------|------|-------------|
| `count` | integer | Number of observations in this hexagon |
| `geom` | Polygon | Hexagon boundary (flat-top orientation) |

---

## Actions

Base path: `/actions/`

These are traditional form-POST endpoints that perform a mutation and redirect. All require authentication.

---

### Delete alert

```
POST /actions/delete_alert
```

Deletes an alert owned by the authenticated user.

**Authentication** - Required

**Form parameters**

| Parameter | Description |
|-----------|-------------|
| `alert_id` | Alert ID to delete |

**Response** - HTTP redirect

**Errors**

- `403 Forbidden` - alert not owned by the current user

---

### Mark observation as unseen

```
POST /actions/mark-observation-as-unseen
```

Marks a single observation as unseen for the authenticated user.

**Authentication** - Required

**Form parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `observationId` | Yes | Observation ID |
| `originUrl` | No | URL to redirect to after the action |

**Response** - HTTP redirect (to `originUrl` if provided, otherwise to a default page)

---

### Delete own account

```
POST /actions/delete-own-account
```

Permanently deletes the authenticated user's account and all associated data, then logs the user out.

**Authentication** - Required

**Response** - HTTP redirect to homepage

---

### Delete area

```
POST /actions/area/delete/<id>
```

Deletes a user-owned area.

**Authentication** - Required

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `id` | Area ID |

**Response** - HTTP redirect

**Errors**

- `403 Forbidden` - area not owned by the current user
- Shows an error message (and does not delete) if one or more alerts still reference the area
