# Plan: Approaching Observations Feature

**Status**: Planning - not yet implemented
**Last updated**: 2026-03-12 (all open questions resolved)

---

## Feature Summary

Add a proximity mode to area-based filtering. When a user selects an area in an alert (or in the
main observation search), they can now choose:

- `inside` - observations located within the polygon (current behaviour, default)
- `approaching` - observations NOT inside the polygon, but within a configurable distance of its
  boundary
- `both` - union of the two above

All other system behaviour (alerts without areas, WFS endpoint, public API, email frequency logic,
ObservationUnseen tracking) stays identical. Only the spatial predicate changes.

---

## Decisions Made

### Buffer distance unit: meters, stored as km (FloatField)

User-facing value is in km. Stored on `Alert` as `approaching_distance_km` (FloatField, nullable).

### Buffer applies to the union of all selected areas

`Alert.areas` is a M2M. The current code already unions all selected areas into one geometry
(`AggregateUnion`). The mode and distance apply uniformly to that union. If a user wants different
buffers per area, the answer is: create separate alerts.

### No geography cast via ORM dwithin lookup - use raw SQL

**Critical finding from spike (2026-03-12):**

GeoDjango's `location__dwithin=(polygon, D(m=5000))` on an SRID 3857 PointField passes the
distance in SRID 3857 units, not meters. At Belgian latitude (~51 deg N):

- 5000 SRID 3857 units = 3161 m actual (37% error)
- Scale factor: ~1.582 SRID 3857 units per real meter

PostGIS also refuses `::geography` directly on SRID 3857 ("Only lon/lat coordinate systems are
supported in geography"). You must `ST_Transform` to SRID 4326 first.

**The correct SQL for a metric buffer:**

```sql
ST_DWithin(
    ST_Transform(observation.location, 4326)::geography,
    ST_Transform(area_union, 4326)::geography,
    <distance_in_meters>
)
```

The GiST index on `location` (SRID 3857) still assists via bounding-box pre-filter before the
exact distance check. Confirm with EXPLAIN ANALYZE on first implementation.

### is_approaching NOT stored on ObservationUnseen

The feature is purely a filter - observations either appear in results or they don't. There is no
need to label observations as "approaching" vs "inside" in the database or UI. This keeps the
schema minimal and avoids complicating the unseen/seen tracking logic.

---

## Backend Changes Required

### 1. Alert model (`dashboard/models.py`)

Add after the `areas` M2M field (around line 982):

```python
AREA_FILTER_INSIDE = "inside"
AREA_FILTER_APPROACHING = "approaching"
AREA_FILTER_BOTH = "both"
AREA_FILTER_MODE_CHOICES = [
    (AREA_FILTER_INSIDE, "Inside the area"),
    (AREA_FILTER_APPROACHING, "Close to the area (not inside)"),
    (AREA_FILTER_BOTH, "Inside or close to the area"),
]

area_filter_mode = models.CharField(
    max_length=20,
    choices=AREA_FILTER_MODE_CHOICES,
    default=AREA_FILTER_INSIDE,
)
approaching_distance_km = models.FloatField(
    null=True,
    blank=True,
    help_text="Required when area_filter_mode is 'approaching' or 'both'. Distance in km.",
)
```

Migration: simple AddField x2, no data migration needed. Existing alerts default to `inside`.

Add model-level validation in `Alert.clean()`:
- `approaching_distance_km` must be set (and > 0) when mode is not `inside`
- `approaching_distance_km` must be null when mode is `inside`
- mode must be `inside` when no areas are selected


### 2. ObservationManager.filtered_from_my_params() (`dashboard/models.py`)

Add two new parameters: `area_filter_mode="inside"` and `approaching_distance_km=None`.

Replace the current spatial block (lines ~396-400):

```python
# CURRENT
if areas_ids:
    combined_areas = Area.objects.filter(pk__in=areas_ids).aggregate(
        area=AggregateUnion("mpoly")
    )["area"]
    qs = qs.filter(location__within=combined_areas)
```

With:

```python
# NEW
if areas_ids:
    combined_areas = Area.objects.filter(pk__in=areas_ids).aggregate(
        area=AggregateUnion("mpoly")
    )["area"]

    if area_filter_mode == Alert.AREA_FILTER_INSIDE or not approaching_distance_km:
        qs = qs.filter(location__within=combined_areas)
    else:
        buffer_m = approaching_distance_km * 1000
        ewkb = combined_areas.ewkb
        dwithin_sql = (
            "ST_DWithin("
            "ST_Transform(dashboard_observation.location, 4326)::geography, "
            "ST_Transform(ST_GeomFromEWKB(%s), 4326)::geography, "
            "%s"
            ")"
        )
        if area_filter_mode == Alert.AREA_FILTER_APPROACHING:
            qs = qs.extra(
                where=[
                    dwithin_sql,
                    "NOT ST_Within(dashboard_observation.location, ST_GeomFromEWKB(%s))",
                ],
                params=[ewkb, buffer_m, ewkb],
            )
        else:  # AREA_FILTER_BOTH
            qs = qs.extra(where=[dwithin_sql], params=[ewkb, buffer_m])
```

The `extra()` call is safe here: geometry values are passed as parameterised SQL placeholders
(%s), not string-interpolated.

**NOTE**: `filtered_from_my_params` is called from `Alert.observations()` and
`Alert.unseen_observations()`. Those need to pass the new fields through:

```python
# Alert.observations() (line ~1082)
def observations(self):
    return Observation.objects.filtered_from_my_params(
        ...
        areas_ids=[a.pk for a in self.areas.all()],
        area_filter_mode=self.area_filter_mode,
        approaching_distance_km=self.approaching_distance_km,
        ...
    )
```


### 3. JinjaSQL fragment in views/maps.py

The SQL template used for map tile rendering must stay in sync with the ORM path (see warning at
models.py:376).

Current (line ~40):

```sql
{% if area_ids %}
    AND ST_Within(obs.location, areas.mpoly)
{% endif %}
```

New:

```sql
{% if area_ids %}
    {% if area_filter_mode == 'inside' or not approaching_distance_km %}
        AND ST_Within(obs.location, areas.mpoly)
    {% elif area_filter_mode == 'approaching' %}
        AND ST_DWithin(
            ST_Transform(obs.location, 4326)::geography,
            ST_Transform(areas.mpoly, 4326)::geography,
            {{ approaching_distance_km * 1000 }}
        )
        AND NOT ST_Within(obs.location, areas.mpoly)
    {% else %}  {# both #}
        AND ST_DWithin(
            ST_Transform(obs.location, 4326)::geography,
            ST_Transform(areas.mpoly, 4326)::geography,
            {{ approaching_distance_km * 1000 }}
        )
    {% endif %}
{% endif %}
```

The `area_filter_mode` and `approaching_distance_km` values need to be threaded through the view
context that builds the JinjaSQL params dict. Trace the call chain from the map tile view down to
confirm which dict keys to add.


### 4. create_unseen_observations() (`dashboard/models.py`, line ~243)

This is the import hot path. It currently builds a combined spatial filter for all alerts
belonging to a user (O(users) queries total). With different `area_filter_mode` values per alert,
we cannot merge alerts with different modes into a single spatial query.

**New grouping strategy**: group user alerts by `(area_filter_mode, approaching_distance_km)`
before building the combined area union. For each group, run one spatial query.

In practice, most users will have at most one or two distinct `(mode, distance)` combinations, so
this stays near O(users).

Pseudo-code:

```python
# Within the per-user loop, after collecting user's alerts:
alerts_by_spatial = {}
for alert in user_alerts:
    key = (alert.area_filter_mode, alert.approaching_distance_km)
    alerts_by_spatial.setdefault(key, []).append(alert)

for (mode, distance_km), alerts_group in alerts_by_spatial.items():
    # Collect all area IDs for this group
    # Build combined species/dataset/etc. filter (existing logic)
    # Apply spatial filter matching the mode
    # Append to unseen_to_create
```

The existing bulk_create with `ignore_conflicts=True` remains correct. If the same observation
matches two alerts for the same user (one "inside", one "approaching"), process the "inside"
group first so it wins on conflict.


### 5. Alert CRUD (views/internal_api.py)

- `_create_or_update_alert()` must accept and save the two new fields.
- The GET endpoint for a single alert must return them.
- Add server-side validation matching `Alert.clean()`.


### 6. filters_from_request() / helpers.py

The main-page search filters are built from request parameters. Add parsing for:
- `area_filter_mode` (string, validated against choices)
- `approaching_distance_km` (float, positive)

These are passed down to `filtered_from_my_params()` and to the JinjaSQL map context.

---

## Frontend Changes Required

### TypeScript interfaces (assets/ts/interfaces.ts)

`DashboardFilters` (or equivalent) needs two new optional fields:

```typescript
areaFilterMode?: "inside" | "approaching" | "both";
approachingDistanceKm?: number;
```

### Alert form (assets/ts/components/AlertForm.vue or similar)

- Add a select/radio group for area filter mode, shown only when at least one area is selected.
- Add a numeric input for distance (km), shown only when mode is `approaching` or `both`.
- Disable/hide both controls when no areas are selected; reset to defaults on area deselection.
- Client-side validation: distance required and > 0 when mode is not `inside`.
- Consider a reasonable max value in the UI (e.g., 500 km) matching the server-side cap.

### Main observation search / filter panel

Same controls as the alert form. Likely reuses the same Vue component or at least the same logic.

### Map display (deferred - nice-to-have)

For the MVP, the map shows/hides observations based on the filter with no visual distinction
between "inside" and "approaching" observations. A visual distinction (different colour or icon)
would require:
- A flag in the MVT tile data or a second tile layer
- Frontend styling logic in the Mapbox style spec

Out of scope for the first iteration.

### i18n

New strings needed in English, French, and Dutch for:
- "Inside the area"
- "Close to the area (not inside)"
- "Inside or close to the area"
- "Proximity distance (km)"
- Validation error messages

---

## Resolved Questions

1. **Max buffer distance**: Cap at **500 km**. Enforce server-side in `Alert.clean()` and in the
   internal API validation. Mirror the limit in the frontend input (max attribute).

2. **Map visual distinction**: **Not needed.** No second tile layer, no different pin colour.
   Observations simply appear or don't based on the active filter.

3. **Alert/email area description wording**: Add a human-readable description to the areas section
   wherever it currently lists area names. Format:
   - `inside` mode: `"Areas: inside 'Foret de Soignes'"` (current implicit behaviour, now explicit)
   - `approaching` mode: `"Areas: within 10 km of 'Belgium'"`
   - `both` mode: `"Areas: inside or within 10 km of 'Belgium'"`
   This affects the alert detail view and email body - anywhere areas are currently rendered as a
   plain list of names. Requires a small helper method on `Alert` that formats the area description
   string based on `area_filter_mode` and `approaching_distance_km`.

4. **EXPLAIN ANALYZE**: Still required before merging. Run on staging/production-sized data and
   document result here.

---

## Testing Requirements

### Model validation (`Alert.clean()`)

- Mode `approaching` or `both` without `approaching_distance_km` set -> ValidationError
- Mode `approaching` or `both` with `approaching_distance_km <= 0` -> ValidationError
- Mode `approaching` or `both` with `approaching_distance_km > 500` -> ValidationError
- Mode `inside` with `approaching_distance_km` set -> ValidationError
- Mode `approaching` or `both` with no areas selected -> ValidationError
- All valid combinations pass without error

### filtered_from_my_params() - spatial correctness

These are the most critical tests. Use real PostGIS geometries with known coordinates so distances
are verifiable. For each of the three modes, create:
- An observation clearly inside the area
- An observation clearly outside but within the buffer distance
- An observation clearly outside and beyond the buffer distance

Then assert which observations appear in the queryset for each mode. Cover:

- `inside`: only the inside observation appears
- `approaching`: only the buffer observation appears (inside one is excluded)
- `both`: inside and buffer observations appear; beyond-buffer does not

Also test distance accuracy: place an observation at a known real-world distance (e.g., 4.9 km
and 5.1 km from a polygon edge) and verify the 5 km buffer boundary is respected within
reasonable tolerance (the ST_Transform + geography approach should be accurate to <1%).

### JinjaSQL fragment / map tile path

Verify that for the same filter parameters, the raw SQL path (maps.py) returns the same set of
observation IDs as `filtered_from_my_params()`. This is the consistency check the existing
warning at models.py:376 calls for. One integration test per mode (inside / approaching / both)
is sufficient.

### create_unseen_observations() - import hot path

- Observations matching an alert's approaching filter become ObservationUnseen entries
- Observations outside the buffer do not
- When a user has two alerts with different modes/distances for the same area, both are handled
  correctly and independently
- The "inside wins over approaching" conflict resolution: if the same observation matches one
  alert as inside and another as approaching for the same user, the ObservationUnseen entry is
  created (not skipped) and no duplicate is created

### Alert area description helper

- `inside` mode, one area -> `"inside 'Foret de Soignes'"`
- `inside` mode, two areas -> `"inside 'Foret de Soignes' or 'Zonienwoud'"`
- `approaching` mode -> `"within 10 km of 'Belgium'"`
- `both` mode -> `"inside or within 10 km of 'Belgium'"`

### What NOT to test separately

The geography distance math itself (ST_DWithin accuracy) is a PostGIS responsibility, not ours.
The spike already validated the approach. No need for exhaustive coordinate arithmetic tests.

---

## Implementation Phases

| Phase | Work | Notes |
|---|---|---|
| 0 - DONE | Spike: ORM dwithin does not cast to geography; quantified SRID 3857 distortion at 51 deg N (37% error) | Done 2026-03-12 |
| 1 | Model: add `area_filter_mode` + `approaching_distance_km` to Alert + migration | Low risk |
| 2 | Backend: update `filtered_from_my_params()`, `Alert.observations()`, `Alert.unseen_observations()` | Medium |
| 3 | Backend: update JinjaSQL fragment in maps.py | Must be done together with Phase 2 |
| 4 | Backend: update `create_unseen_observations()` grouping logic | Medium |
| 5 | Backend: alert CRUD API (internal_api.py) + `filters_from_request()` | Low |
| 6 | Frontend: TypeScript interfaces + alert form controls | Medium |
| 7 | Frontend: main search filter panel | Low (reuses alert form work) |
| 8 | Tests: integration tests verifying all three query paths return identical result sets | High priority |
| 9 | Performance: EXPLAIN ANALYZE on staging/production data | Before merging |

Phases 2 and 3 must be implemented and tested together to avoid the map/table inconsistency
described in the warning at models.py:376.

---

## Files to Touch

| File | Change |
|---|---|
| `dashboard/models.py` | Alert model fields, `filtered_from_my_params()`, `Alert.observations()`, `create_unseen_observations()` |
| `dashboard/migrations/XXXX_alert_area_filter.py` | New migration (auto-generated) |
| `dashboard/views/maps.py` | JinjaSQL spatial fragment |
| `dashboard/views/helpers.py` | `filters_from_request()`, JinjaSQL params dict |
| `dashboard/views/internal_api.py` | Alert CRUD |
| `assets/ts/interfaces.ts` | DashboardFilters type |
| Alert form Vue component | New mode selector + distance input |
| Main filter panel Vue component | Same controls |
| Alert detail template | Area description string (inside / within X km of / ...) |
| Email template | Same area description string |
| Locale files (en/fr/nl) | New i18n strings |
