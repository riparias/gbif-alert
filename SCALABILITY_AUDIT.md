# Scalability Audit - 10x growth

This document inspects the API and the observation import process and lists the
codepaths that are likely to become problematic if the data volume grows by
roughly an order of magnitude (mostly observations, with some growth in users
and alerts as well).

## Working assumptions

The audit assumes today's order of magnitude (based on
`APPROACHING_OBSERVATIONS_PLAN.md` and the staging dataset referenced there) is
approximately:

- ~1 - 10 M observations
- a few hundred users, a few thousand alerts
- a few thousand `ObservationUnseen` rows per active user

A 10x scenario therefore looks roughly like:

- 10 - 100 M observations
- a few thousand users, ~10k - 50k alerts
- `ObservationUnseen`: potentially 10s of millions of rows total (it scales
  with `unseen_observations * users_with_alerts`, capped per user by the
  `notification_delay_days`)

Findings are sorted by severity. Each entry says what the problem is, where it
lives, why 10x makes it worse, and a realistic mitigation framed in the way the
user requested ("query optimization", "more hardware", "rewrite", or "limit
the feature").

---

## Critical (will hurt at 10x, fix first)

### 1. `User.obs_match_alerts()` - N+1 on every observation detail view

- **Where:** `dashboard/models.py:62-67`
- **Called from:**
  - `dashboard/api_v2.py:409` (`observation_detail`, `can_be_marked_unseen`)
  - `dashboard/models.py:713` (`Observation.mark_as_unseen_by`)

```python
def obs_match_alerts(self, obs):
    for alert in self.alert_set.all():
        if alert.observations().filter(pk=obs.pk).exists():
            return True
    return False
```

Each iteration calls `alert.observations()` which rebuilds the full
`filtered_from_my_params()` queryset (species + dataset + spatial + date +
verified filters), then probes it with `.filter(pk=obs.pk).exists()`. Today:
1 user with 5 alerts = 5 spatially-filtered exists() probes. At 10x with power
users having 20+ alerts, that is 20+ probes per detail view, each one going
through PostGIS for alerts that have area filters.

**Mitigation - query rewrite (cheap and high impact):**
The whole loop can be replaced with a single query: "does any alert belonging
to this user match this observation?". The simplest correct rewrite is to
build a single `Q()` of all the user's alert criteria, but that is hard
because each alert has its own filters. A cleaner option is to invert the
question: instead of "does the obs match the alert", check "is this obs in any
queryset that the user's alerts produce". That can be done by computing, in
one query per request, the set of alert IDs whose observations() qs contains
this obs - using a single UNION ALL of `alert.observations().filter(pk=obs.pk)`
per alert. That is still O(alerts) but in one round trip.

A better long term fix: store the alert <-> observation match as a denormalized
row at import time (similar to what `create_unseen_observations` already does
for `ObservationUnseen`). Then `obs_match_alerts` becomes a single `EXISTS`
on `ObservationUnseen` (or a new `AlertMatch` table) for this user/observation,
which is O(1).

---

### 2. `Alert.unseen_observations_count` - one COUNT(*) per alert per response

- **Where:**
  - `dashboard/models.py:1282-1284` (definition)
  - `dashboard/api_v2.py:532` (`_alert_to_out`, called for every alert returned
    by `/api/v2/alerts/`, `/api/v2/alerts/{id}/`, create, and update)
  - `dashboard/models.py:1325` and `:1298` (email notification command)

```python
"unseenCount": alert.unseen_observations().count(),
```

Each `unseen_observations()` call rebuilds the full filtered queryset (with
the spatial filter, the species/dataset filter, AND the unseen status
subquery) and then runs a `SELECT COUNT(*)`. The `/api/v2/alerts/` list
endpoint then iterates over the prefetched alerts, so for a user with 20
alerts the response is 20 separate aggregate queries, each scanning a sizable
slice of the observation table.

**Mitigation - feature design + cache:**
- Best fix: precompute `unseen_count` per `(alert, user)` and store it on the
  Alert model (or in a small `AlertUnseenCount` table). Update incrementally:
  on import, the same code that fills `ObservationUnseen` already iterates
  per user/alert group - it can `INCREMENT` the counter at the same time. On
  `mark_as_seen_by` and `mark_as_unseen_by`, decrement/increment.
- Cheap fix without a schema change: cache the count for a short window
  (e.g., 60 seconds) keyed on `(alert_id, user_id, last_data_import_id)`. The
  number is rarely time-critical: if a user just marked obs as seen, a small
  refresh delay is acceptable.
- If neither is acceptable, **limit the feature**: do not return `unseenCount`
  in the `/api/v2/alerts/` list at all - only on the alert detail endpoint.
  The list page can show an "?" badge that resolves lazily once the user
  hovers/clicks.

---

### 3. `Observation.date` is not indexed, but is filtered/sorted/aggregated everywhere

- **Where:** `dashboard/models.py:665-669` (Meta.indexes only contains
  `stable_id`)
- **Used by:**
  - `filtered_from_my_params()` (`models.py:469-472`) - `date__gte/lte`
  - `observations_list()` default sort (`api_v2.py:319`) is `-date, -pk`
  - `observations_histogram()` (`api_v2.py:378-382`) `TruncMonth("date")`
    + `Count`
  - `create_unseen_observations()` (`models.py:318` and similar) date
    threshold filter

Note: foreign keys (`species`, `source_dataset`, `basis_of_record`,
`data_import`, `initial_data_import`) are auto-indexed by Django, so the
common single-column FK filters are fine. The hot missing index is `date`.

At 10x, the default landing page sorts 100M rows by `-date` and reads the
top 20. Without an index on `date`, that is a full sort on a hundred-million
row table.

**Mitigation - add indexes (cheap, low risk):**
- Add `models.Index(fields=["-date", "-id"], name="dashboard_o_date_idx")`
  to support the default sort and the date range filter in one go.
- Optionally add a partial index `WHERE verified = true` if the verified
  filter ends up being heavily used, but verify with `pg_stat_user_tables`
  first.
- Consider compound indexes for the most common combinations after measuring
  in production: `(species_id, date)` and `(source_dataset_id, date)` are the
  obvious candidates, but they cost insert performance during the import
  batches, so do it only if the single-column `date` index is not enough.

---

### 4. `migrate_unseen_observations()` loads every unseen row into Python memory

- **Where:** `dashboard/models.py:507-619`, especially `:514-526`

```python
unseen_observations = ObservationUnseen.objects.select_related(
    "observation", "observation__data_import", "user"
).all()
...
unseen_list = list(unseen_observations)
```

Today this works because there are at most a few hundred thousand unseen
rows. At 10x, an active deployment can have tens of millions of unseen rows
(`unseen_observations * users_with_alerts`, capped per user by
`notification_delay_days`). Each row materializes a Python object plus the
joined `Observation`, `DataImport`, and `User`, which is multiple kilobytes
per row. 50M rows * 1 KB = 50 GB of resident memory in the import worker.

**Mitigation - rewrite to streaming + SQL:**
The function actually only needs two pieces of information per unseen row:
the `stable_id` and the new observation id in the current import. Both can
be computed in pure SQL:

```sql
-- Update unseen rows pointing to obsolete observations to point to the new one
UPDATE dashboard_observationunseen ou
   SET observation_id = new_obs.id
  FROM dashboard_observation old_obs
  JOIN dashboard_observation new_obs
    ON new_obs.stable_id = old_obs.stable_id
   AND new_obs.data_import_id = %s          -- current import
 WHERE ou.observation_id = old_obs.id
   AND old_obs.data_import_id <> %s;

-- Delete unseen rows whose observation has no successor in the new import
DELETE FROM dashboard_observationunseen
 WHERE observation_id IN (
       SELECT old_obs.id
         FROM dashboard_observation old_obs
    LEFT JOIN dashboard_observation new_obs
           ON new_obs.stable_id = old_obs.stable_id
          AND new_obs.data_import_id = %s
        WHERE old_obs.data_import_id <> %s
          AND new_obs.id IS NULL
       );
```

That moves the migration cost from "O(rows) Python + memory" to "two
set-based SQL statements that the database planner already knows how to
execute". It also removes the `select_related("user")` join, which is
currently dead weight (the user pk is never used, only `observation.stable_id`).

---

### 5. `Observation.objects.exclude(data_import=current).delete()` at import end

- **Where:** `dashboard/management/commands/import_observations.py:500`

After every import, every observation row from the previous import is
deleted. With cascade deletes on `ObservationComment` and `ObservationUnseen`
this is a single DELETE that touches the entire previous dataset (~100M rows
at 10x) in one statement, which means one giant transaction that holds locks
and bloats the WAL. The materialized view refresh that follows then has to
re-read the same table.

**Mitigation - batch the delete + reorder:**
- Delete in chunks of, say, 100k rows in a loop: `Observation.objects.filter(
  data_import_id=old_id).only("pk")[:100_000].delete()`. Vacuum/analyze after.
- A cheaper alternative: instead of a hard delete, mark the old `data_import`
  as `superseded=True` and have the API filter on
  `data_import__superseded=False`. Then run an offline job (outside the
  import transaction) that batch-deletes superseded rows. This decouples the
  user-visible "import done" moment from the slow cleanup.

This is the kind of fix where "more RAM" does not help: the bottleneck is
WAL throughput and lock duration, not memory.

---

## High (noticeable degradation, plan for it)

### 6. `filtered_from_my_params()` unseen-status subquery

- **Where:** `dashboard/models.py:492-497`

```python
ous = ObservationUnseen.objects.filter(user=user)
if status_for_user == "unseen":
    qs = qs.filter(observationunseen__in=ous)
```

This generates a join + IN subquery against `ObservationUnseen`. The unique
constraint on `(observation, user)` (`models.py:1011-1014`) does provide an
index on `(observation_id, user_id)` in that order, but **not** the
`(user_id, observation_id)` index that this query actually wants - the
optimizer wants to start from "rows in `ObservationUnseen` where user = me"
and join into observations.

**Mitigation - one targeted index (cheap):**
Add `models.Index(fields=["user", "observation"])` to `ObservationUnseen.Meta`.
At 10x scale this single index turns the unseen filter from a hash-join
seq scan into an index lookup of "rows for this user". The space cost is
bounded by the size of `ObservationUnseen` itself, which is the smaller side
of the join.

Once the index is there, also rewrite the ORM query to drop the subquery:

```python
qs = qs.filter(observationunseen__user=user)   # status == "unseen"
qs = qs.exclude(observationunseen__user=user)  # status == "seen"
```

`__user=user` reduces to `WHERE user_id = %s` against the unseen table and
lets the planner use the new index directly, instead of materializing the
`ous` subquery.

---

### 7. `observations_list` distinct counts on every request

- **Where:** `dashboard/api_v2.py:310-314`

```python
aggregates = qs.aggregate(
    total=Count("pk"),
    species_count=Count("species_id", distinct=True),
    datasets_count=Count("source_dataset_id", distinct=True),
)
```

`COUNT(*)` is fine, but the two `COUNT(DISTINCT ...)` aggregates force a
sort or hash over the entire filtered set. On the unfiltered landing page
that is the entire observation table.

**Mitigation - rethink the contract:**
- These two counts feed the "X species, Y datasets" badge in the sidebar.
  That information is much less time-critical than the row count. Move it
  to a separate endpoint that is only fetched lazily (when the user opens
  the histogram or the dataset filter), and compute it from the `Dataset`
  and `Species` tables joined to a sampled observation slice.
- Or precompute "species count / dataset count per filter combination" only
  for the trivial cases (no filters, single species, single dataset). Today
  > 90% of landing page hits use no filter at all, and for that case the
  numbers are constants between two imports.
- "Just add an index" does not really help here: a `COUNT(DISTINCT)` on a
  large filtered set is fundamentally a sort of the join output. This is a
  feature-design problem.

---

### 8. `observations_histogram` aggregates the entire filtered table per request

- **Where:** `dashboard/api_v2.py:359-388`

```python
qs.annotate(month=TruncMonth("date")).values("month").annotate(total=Count("id")).order_by("month")
```

At 1x this is fine because the staging dataset is ~1M rows. At 10x the
histogram on the unfiltered landing page does a `TruncMonth + GROUP BY`
over 100M rows on every page load. Adding a `date` index (#3 above) helps
the access path but the aggregation cost is still O(rows in the filter).

**Mitigation - precompute + cache:**
- For the unfiltered case, materialize "(year_month, count)" once per
  data import. Refresh it as part of `create_or_refresh_materialized_views`
  (already wired in `import_observations.py:508`). Serve the materialized
  result directly when no filters are applied; recompute live only when
  filters are present.
- For filtered cases, cache the response in Redis keyed on the canonical
  filter signature for ~5 minutes. Filters tend to repeat: most users hit
  the same handful of saved filter combinations.

---

### 9. Map vector tiles compute the full filter on every tile request

- **Where:** `dashboard/views/maps.py:172-243` (`mvt_tiles_observations` and
  `mvt_tiles_observations_hexagon_grid_aggregated`)

Each tile request runs `JINJASQL_FRAGMENT_FILTER_OBSERVATIONS` which is the
SQL twin of `filtered_from_my_params()`. A typical map view fires 10 - 30
tile requests in parallel, each running the full filter against the
observation table. The hex aggregation tile already has a careful tile-
envelope optimization (`maps.py:217-238`), but the non-aggregated tile
endpoint does not.

At 10x, the dominant cost is no longer the tile envelope intersection - it
is the filter (`species`/`dataset`/`status`) being re-applied 30 times per
viewport.

**Mitigation - tile cache + small rewrite:**
- Add an HTTP cache layer (Varnish, CloudFront, or `django-cachalot` /
  `django-redis-cache`) keyed on `(zoom, x, y, filter_hash, user_id_for_unseen)`.
  Tiles are immutable between data imports, so the cache TTL can be "until
  the next import" with explicit purge after `import_observations`.
- The non-aggregated tile endpoint (`mvt_tiles_observations`) already has
  no tile-envelope WHERE clause - add one mirroring what the aggregated
  endpoint does (`maps.py:233-237`). Without it, the non-aggregated tile
  scans the entire filter result and clips client-side via `ST_AsMVTGeom`,
  which is wasteful at high zoom levels.

---

### 10. `User.has_alerts_with_unseen_observations` - N+1 in the navbar

- **Where:** `dashboard/models.py:75-81`

```python
@property
def has_alerts_with_unseen_observations(self) -> bool:
    for alert in self.alert_set.all():
        if alert.has_unseen_observations:
            return True
    return False
```

`alert.has_unseen_observations` itself calls `unseen_observations_count`
(see #2), which does a `COUNT(*)`. If this property is referenced in the
navbar template (to show a "you have alerts" badge), every authenticated
page load runs `O(alerts) * COUNT(*)`. Worth verifying whether this is
actually called on every render - if yes, it is a critical issue and
belongs above; if not, it stays here as a latent footgun.

**Mitigation - same as #2:**
If unseen counts get cached/denormalized for #2, this method becomes a
single `EXISTS` query. As a stopgap, short-circuit it to a single
`Alert.objects.filter(user=user).filter(<unseen exists>).exists()` rather
than iterating in Python.

---

### 11. `create_unseen_observations` - in-Python row construction

- **Where:** `dashboard/models.py:292-435`, especially the loop at `:429-430`

```python
for obs in group_obs_qs:
    unseen_to_create.append(ObservationUnseen(observation=obs, user=user))
```

The recent optimization (see `IMPORT_OBSERVATIONS_OPTIMIZATION.md`) already
groups users into spatial groups so the queries are O(users * spatial groups)
instead of O(users * alerts). But the row construction is still in Python:
for each user, every matching observation is pulled into Python only to be
turned into an `ObservationUnseen` instance and bulk-inserted. At 10x with
1M new observations per import * a few thousand users with overlapping
filters, this loop allocates billions of Python objects.

**Mitigation - rewrite as `INSERT ... SELECT`:**
The whole loop can be replaced by one statement per user-group:

```sql
INSERT INTO dashboard_observationunseen (observation_id, user_id)
SELECT obs.id, %s
  FROM dashboard_observation obs
 WHERE obs.data_import_id = %s
   AND obs.species_id  = ANY(%s)
   AND obs.source_dataset_id = ANY(%s)
   AND obs.date > %s
   AND ST_Within(obs.location, %s::geometry)
ON CONFLICT (observation_id, user_id) DO NOTHING;
```

This keeps the data inside PostgreSQL the whole time. Memory in the import
worker becomes O(1) per user-group instead of O(matching observations).

---

### 12. `Dataset.save()` walks every observation in the dataset

- **Where:** `dashboard/models.py:175-183`

If a dataset's `gbif_dataset_key` changes (rare, but possible during a
manual fix), the override iterates `for occ in self.observation_set.all():`
and re-saves each observation to recompute its `stable_id`. With ~1M
observations per dataset at 10x, that single save() call locks up the
admin/shell for hours.

**Mitigation - replace the loop with a single UPDATE:**
The `stable_id` is `sha1("occ_id: <occurrence_id> d_id: <dataset_key>")`.
That can be computed in PostgreSQL with `digest(...)` from `pgcrypto` and
applied to all rows in one statement. Or, more conservatively, run the
recomputation as a background job that batches by `pk` ranges. This is
"feature borderline" - rotating a `gbif_dataset_key` is rare enough that
the right answer might just be to forbid it in the admin and require a
re-import.

---

## Medium

### 13. `User.empty_all_comments` runs one save() per comment

- **Where:** `dashboard/models.py:97-100`, called from `pre_delete` signal at
  `:108-110`

```python
def empty_all_comments(self) -> None:
    for comment in self.observationcomment_set.all():
        comment.make_empty()
```

At 10x, a power user might have thousands of comments. Each `make_empty()`
likely issues an UPDATE. Per-row UPDATE is fine for hundreds, painful for
hundreds of thousands.

**Mitigation - one UPDATE:**
`ObservationComment.objects.filter(author=self).update(text="")` (or
whatever `make_empty` actually sets). Single statement, no Python loop.

---

### 14. Approaching-mode buffer queries with large radii

- **Where:** documented in `APPROACHING_OBSERVATIONS_PLAN.md:330-410`. Code:
  `dashboard/models.py:479-488`

The PR added a geography `GIST` index (migration 0029) which makes 3 km
buffers fast. At 50 km buffers and 1M observations the plan documents
~37 s queries, because the index returns ~568 k candidates that all need
exact distance recomputation. At 10x that becomes minutes.

**Mitigation - limit the feature, not the query:**
- Cap `approaching_distance_km` to a hard maximum (5 km? 10 km?) above
  which the API rejects the request. The plan document already hints at
  this.
- For users who really need wide buffers, expose them via an asynchronous
  "report" workflow (background job that emails a CSV) instead of the
  interactive map.
- More hardware/RAM does not help: the bottleneck is geometry math, which
  is CPU-bound and parallelizes badly inside a single PostgreSQL backend.

---

### 15. `ObservationsView` page-load fans out 6+ requests in parallel

- **Where:**
  - `assets/frontend/pages/IndexPage.vue` calls `FilterSidebar`, `HistogramBrush`,
    `ObservationsView`, plus `/api/v2/page-fragments/welcome_text/`
  - The sidebar fetches `/api/v2/species/`, `/api/v2/datasets/`,
    `/api/v2/areas/`, `/api/v2/basis-of-record/`, `/api/v2/data-imports/`

Each one of those is a small query in isolation, but together they put
6 - 8 requests on the wire on every cold landing-page hit, all in parallel.
The most expensive of those (#7 distinct counts, #8 histogram, #9 map
tiles) are the ones already discussed above; the dropdown lookups are
small but repetitive.

**Mitigation - bundle + cache in the browser:**
- Bundle the dropdown endpoints into a single `/api/v2/bootstrap/` that
  returns species + datasets + basis of record + areas in one round trip,
  with a long browser cache (these change at most once per import).
- Add an `ETag` or `Last-Modified` based on the most recent `DataImport.start`
  so clients can revalidate cheaply.

This is purely a frontend/contract change - no schema work.

---

### 16. `migrate_unseen_observations` `bulk_update()` is unbounded

- **Where:** `dashboard/models.py:604` (and `:614` for `bulk_delete`)

Even after the rewrite suggested in #4, if you stay with the current
"compute then bulk_update" approach, `bulk_update` of 1M+ rows in a single
call materializes a giant `CASE WHEN id = ... THEN ...` statement on the
client side and ships it to PostgreSQL. Django's bulk_update has a
`batch_size` parameter; it is not used here.

**Mitigation - cheap:** pass `batch_size=10_000` to `bulk_update()` and
`bulk_create()` calls inside the import. Already mentioned in
`IMPORT_OBSERVATIONS_OPTIMIZATION.md` as a known concern. The SQL rewrite
in #4 makes this moot.

---

### 17. Materialized view refresh time at end of import

- **Where:** `dashboard/management/commands/import_observations.py:508`,
  `create_or_refresh_materialized_views`

The hexagon materialized views (`hexa_*`) are rebuilt from scratch at the
end of every import. The rebuild time is O(observations * zoom levels).
At 10x and a single zoom level it is still bounded but climbs into the
tens of minutes.

**Mitigation:**
- The site is in maintenance mode during the import, so this is acceptable
  as long as the import time stays "overnight". If it does not, switch to
  `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requires a unique index on the
  view) so the API can keep serving the previous version while the new one
  builds.
- Alternative: incremental refresh - only rebuild the hex cells whose
  underlying observations actually changed in this import. This requires
  tracking changed cells and is a meaningful rewrite, only worth it if
  the full refresh exceeds the import window.

---

### 18. Email notification command - one transaction, many counts

- **Where:** `dashboard/management/commands/send_alert_notifications_email.py`,
  loops over `Alert.objects.all()` and calls `email_should_be_sent_now()`
  + `send_notification_email()`

Each notification eligibility check calls
`unseen_observations_count` (#2), and the email body builder calls
`unseen_observations()` again to grab a sample. For 10k alerts that is
20k+ COUNT queries plus 10k LIMIT queries.

**Mitigation:**
- Once #2 is fixed (cached or denormalized counts), this command
  automatically benefits.
- Independently: `prefetch_related` the alert filters so each iteration
  does not re-fetch species/datasets/areas.
- Run it in parallel by user, not serially over all alerts. Trivially
  parallelizable since each user's alerts are independent.

---

## Low

### 19. `Area.objects.filter(...).aggregate(area=AggregateUnion("mpoly"))` is recomputed per query

- **Where:** `dashboard/models.py:474-476` and `dashboard/views/maps.py:137-143`

The combined area geometry is rebuilt on every observation list, every
histogram, and every map tile request, even though it depends only on the
set of `area_ids`. With a few areas this is microseconds; with hundreds
of polygons it adds up.

**Mitigation:** memoize per request (already cheap) or per process with a
short LRU keyed on the sorted tuple of area ids. Low priority.

---

### 20. `obs_match_alerts` short-circuits on first match - keep the order in mind

`User.obs_match_alerts` returns on the first matching alert. If after
fixing #1 you keep iterating in Python for any reason, prefer
`alert_set.order_by("id")` and consider that an alert with restrictive
filters should run last.

This is a micro-optimization and only matters if #1 cannot be replaced
with a single query.

---

## Summary table

| # | Severity | Component | Cost driver | Realistic fix |
|---|----------|-----------|-------------|---------------|
| 1 | Critical | `obs_match_alerts` | N+1 of spatial filter probes | Denormalize alert/obs match, or single UNION query |
| 2 | Critical | `Alert.unseen_observations_count` in `/alerts/` | One COUNT per alert per response | Cache/denormalize unseen count, or drop from list payload |
| 3 | Critical | `Observation.date` not indexed | Sort/filter/aggregate without index | Add `Index(["-date", "-id"])` |
| 4 | Critical | `migrate_unseen_observations` | Loads everything into Python | Rewrite as one UPDATE + one DELETE in SQL |
| 5 | Critical | Bulk delete of old observations | Single huge DELETE in import txn | Batch delete in chunks, or soft-delete + offline cleanup |
| 6 | High | `filtered_from_my_params` unseen subquery | Wrong index direction on `ObservationUnseen` | Add `Index(["user","observation"])` + drop subquery |
| 7 | High | Distinct counts in `observations_list` | `COUNT(DISTINCT)` on full filter | Move to separate lazy endpoint, precompute the no-filter case |
| 8 | High | `observations_histogram` | `TruncMonth + GROUP BY` per request | Materialize per-import, cache filtered cases |
| 9 | High | Map vector tiles | Filter re-applied per tile | HTTP tile cache; add tile envelope to non-aggregated tiles |
| 10 | High | `has_alerts_with_unseen_observations` | N+1 COUNT in navbar | Same fix as #2 |
| 11 | High | `create_unseen_observations` | Python loop building rows | Rewrite as `INSERT ... SELECT` per user-group |
| 12 | High | `Dataset.save()` per-row recompute | O(observations) saves | Single SQL UPDATE, or forbid the operation |
| 13 | Medium | `empty_all_comments` | UPDATE per comment | One bulk UPDATE |
| 14 | Medium | Approaching buffer with large radius | Geometry math | Cap the radius, async report for wide queries |
| 15 | Medium | Frontend cold-load fan-out | 6 - 8 parallel requests | Bundle into `/bootstrap/`, cache by import id |
| 16 | Medium | `bulk_update` no batch_size | Giant single statement | `batch_size=10_000` (or moot after #4) |
| 17 | Medium | Materialized view refresh | O(observations) per import | `REFRESH ... CONCURRENTLY` or incremental |
| 18 | Medium | Email notification command | Sequential COUNTs per alert | Inherits #2 fix; parallelize per user |
| 19 | Low | Area union recomputed | Repeated PostGIS work | Per-request memoize |
| 20 | Low | `obs_match_alerts` ordering | Iteration order | Reorder, only matters if #1 stays |

## What is *not* a problem

A few things the audit deliberately did not flag, in case the reader
expects them:

- **FK column indexes** - Django auto-indexes `ForeignKey` columns by
  default. `species_id`, `source_dataset_id`, `basis_of_record_id`,
  `data_import_id`, and `initial_data_import_id` all have indexes
  already; only `date` and `verified` are missing.
- **`stable_id` lookups during import** - already covered by the explicit
  `stable_id` index added in migration 0020.
- **Geography `GIST` index for approaching mode** - already added in
  migration 0029, and verified in the staging benchmarks documented in
  `APPROACHING_OBSERVATIONS_PLAN.md`.

---

## Suggested order of work

If only a few items can be tackled, the highest value-per-effort sequence is:

1. **Add indexes** (`Observation.date`, `ObservationUnseen.(user, observation)`)
   - one migration, near-zero risk, immediate effect on #3, #6, #8.
2. **Cache or denormalize `Alert.unseen_observations_count`** (#2 + #10 + #18)
   - one place to fix, three problems solved.
3. **Rewrite `migrate_unseen_observations` and `create_unseen_observations` to
   set-based SQL** (#4 + #11) - fixes the import worker memory ceiling.
4. **Replace `obs_match_alerts`** (#1) - the only critical that needs a small
   schema or query design decision.
5. **Batch the post-import delete** (#5) - keeps the import window predictable
   as the dataset grows.

Items 6 onward are improvements rather than blockers and can be tackled
opportunistically.
