# Decisions

An append-only record of how this codebase got where it is: newest entries at
the bottom, never edited once written. Three lines per entry - anything longer
needed a design document instead.

## 2026-07-27 - Observations map height is measured, not computed in CSS

**What:** The map fills the viewport down to the footer via a composable that
measures its own document offset, with a floor at the old fixed 480px.
**Why:** How far down the page the map starts differs per page and depends on
the welcome text, an operator-editable page fragment of unknowable height.
**Rejected:** `calc(100dvh - Npx)`, which needs that offset as a constant;
and aligning the map to the sidebar, which the short alert detail sidebar would
have made shorter rather than taller.

## 2026-07-28 - Index the observation date and the per-user unseen lookup

**What:** Concurrent btree indexes on `Observation(date, id)` and
`ObservationUnseen(user, observation)`, the unseen filter rewritten to use the
latter, and a `VACUUM ANALYZE` closing `import_observations`.
**Why:** The default list sorted the whole table on every load, and the import
rewrites the table wholesale, so index-only scans did a heap fetch per index
entry (199970 of them, 85ms) until something vacuumed.
**Rejected:** Keeping the `observationunseen__in=<subquery>` form, which
self-joins the unseen table and left the new index at zero scans; and a plain
`CREATE INDEX`, which write-locks `dashboard_observation` for its duration.

## 2026-07-28 - Drop the FK index on ObservationUnseen.user_id

**What:** `db_index=False` on the `user` FK, dropping
`dashboard_observationunseen_user_id_c919a467` concurrently in migration 0038.
**Why:** The `(user_id, observation_id)` index added the same day serves every
lookup a `(user_id)` index can, so the FK index was only write cost on a table
the import rewrites in full.
**Rejected:** Also dropping the `observation_id` FK index, redundant against the
same-day unique constraint on `(observation_id, user_id)` by the same argument -
but it is the table's most-scanned index and the smaller one to walk.

## 2026-07-29 - Read DwCA archives through iter_terms

**What:** Upgraded python-dwca-reader to 0.17.1 and switched the import to the
positional iter_terms API, narrowing the discovery pass to three terms.
**Why:** About 12x faster archive parsing, from dropping a per-open full-file
index scan and a 230-key dict built for every row. Worth roughly 5% of a real
import: parsing was never the bottleneck, database work is.
**Rejected:** Upgrading without adopting iter_terms - it left the largest
proportional gain unclaimed for our 230-column archives.

## 2026-07-29 - One query per observation for the replaced-observation lookup

**What:** `Observation.replaced_observation` now does a single `select_related`
slice instead of two `count()` calls, a row fetch and two foreign-key fetches.
**Why:** It runs once per observation on the import's hot path - five queries
per row meant about five million queries on a million-row re-import. Measured
1.25x on the build step, roughly 8 minutes off a million-row import.
**Rejected:** Also deferring the geometry column - measured slower (6.59s vs
5.86s per 3000 rows), because GeoDjango converts it lazily anyway.

## 2026-07-29 - Resolve replaced observations once per chunk

**What:** `_import_all_observations` now pulls raw rows a chunk at a time and
resolves the chunk's stable ids in one `values_list` query, replacing the
per-row lookup; the flush also lost an off-by-one that made the first batch
carry CHUNK_SIZE + 1 rows.
**Why:** 14.1x on the row-building phase (1760s -> 125s projected at 1M rows),
about 27 minutes off a million-row re-import, and it lands within 13s of the
no-lookup floor. Corrects the 1.25x reported for the previous entry, which was
measured at too few rows per run to amortise the fixed archive-open cost - the
real figure for that step alone is 1.38x.
**Rejected:** Keeping the per-row lookup and only widening the chunk size - the
cost was the round trips and the model instantiation per row, not the batch size.

## 2026-07-30 - Benchmark imports against a clone of a real database

**What:** The end-to-end import benchmark now runs against a clone of a real
database (real observation volume, users, alerts, unseen records) rather than a
purpose-built empty one, via `BENCH_DB_NAME` and
`benchmarks/remap_species_to_archive.py`.
**Why:** The empty-table runs reported 1.3-1.4x for the read-path work and 10
minutes for an import that really takes 57-95. With an empty `Observation`
table the per-observation replaced-observation lookup costs one cheap query
instead of five, and `create_unseen_observations` is a no-op with no users - so
the benchmark was measuring a code path production never takes. Re-measured
realistically, the combined change is 2.75x (72.3 -> 26.2 min) and parsing is
3.0% of the original import, not the dominant cost it had been assumed to be.
**Rejected:** Running against the developer database directly - the archive's
taxon keys match none of its species, so the import would have skipped every row
and then deleted all 1,102,040 observations.
## 2026-07-28 - Map tiles filter seen/unseen on (user_id, observation_id)

**What:** The map SQL's status filter is now `user_id = %s` on the joined unseen
row and a `NOT EXISTS` keyed on `(user_id, observation_id)`, instead of the
`id IN (SELECT id ... WHERE user_id = %s)` subquery.
**Why:** The subquery form self-joined the unseen table by primary key just to
read `user_id`, so map tiles missed the `dashboard_ou_user_obs_idx` win the
observation list already got; the map is the heaviest reader of that filter.
**Rejected:** Leaving the map SQL alone as "the ORM path is what matters" - the
two must stay equivalent, and divergent shapes are how they drift apart.

## 2026-07-28 - Species breakdown results tab

**What:** A read-only "Species" results tab, backed by a new
`/observations/species-breakdown/` aggregate endpoint.
**Why:** The sidebar reported how many species matched a search but gave no
way to find out which ones.
**Rejected:** Folding several charts behind a renamed "Chart" tab - it costs
roughly 2.5x for a chart registry serving two charts, and a pie chart is
unreadable at fifty species.

## 2026-08-17 - Expandable details for older data imports

**What:** Older imports on the about-data page became a PrimeVue Accordion whose
panels expand to the same detail block as the most recent import, extracted into
a shared `DataImportDetails` component.
**Why:** The API already returned full details for every import, so the older
ones were summarized purely by the frontend - the data was there but unreachable.
**Rejected:** Dropping the "Show all data imports" button and always rendering
the collapsed accordion - the page's default should stay "one import, fully
described".

## 2026-08-21 - Instance-configurable default area filter on the home page

**What:** A public area can be flagged `is_default_home_filter` in the Django
admin; the home page then opens with it pre-selected, removable like any other
filter via a new `?areaIds=none` sentinel.
**Why:** Instances downloading a bounding box wider than their area of interest
(to spot approaching species) landed visitors on an unfiltered map of the whole
box.
**Rejected:** An env var naming the area - referencing a database row from
`.env` is brittle across databases and renames; and seeding the store without a
URL sentinel, which loses the default on any shared link and resurrects it after
"clear all".
## 2026-08-19 - EU funding acknowledgement, opt-in per instance

**What:** Repository docs and `CITATION.cff` acknowledge the Horizon Europe
grants unconditionally; the footer emblem ships in the codebase but renders only
when an instance sets `SHOW_EU_FUNDING_ACKNOWLEDGEMENT` (default off).
**Why:** The obligation (Grant Agreement Art. 17) is ours, not every deployer's -
an emblem in a shared template would make unrelated instances claim EU support.
**Rejected:** Deployer-supplied footer HTML - the short acknowledgement is
identical on every EU-funded instance, so a boolean beats pasted markup; and
SVG assets - the Commission ships no SVG, and converting the EPS would re-typeset
an emblem that must not be modified.

## 2026-08-21 - Subdivide area geometries for the observation filter

**What:** Every area is stored pre-chopped by `ST_Subdivide` in a derived
`AreaPart` table, and the `inside` filter joins those pieces instead of
intersecting one geometry unioned per request.
**Why:** The GIST index could only prefilter by the union's bounding box, so
filtering ran an exact point-in-polygon test against huge geometries - 16 s for
a 62-area alert over a million observations. Pieces also removed a crash: the
per-request `ST_Union` raised a GEOS TopologyException on self-intersecting
areas.
**Rejected:** Deduplicating with `EXISTS` or with a two-stage `id IN (...)`
query - both defeat the spatial join, measuring 10-30 s and over 40 minutes
against the chosen form's sub-second. A materialized view refreshed at import
time was also rejected: user-created areas would have no pieces until the next
import, forcing a permanent fallback path.

## 2026-08-26 - Auto-deploy the devel instance, not the demo

**What:** The post-build webhook call in `image.yml` now redeploys the `devel`
instance; the demo instance no longer auto-follows the `devel` branch and is
bumped manually to stable releases.
**Why:** The demo is what outsiders evaluate GBIF Alert on, so it should show a
released version rather than whatever last landed on `devel`.
**Rejected:** Keeping both wired (demo and devel each auto-deploying from
`devel`) - that leaves the demo exposed to unreleased regressions, which is the
problem being fixed.

## 2026-08-26 - Full partial update for species, not a tags-only endpoint

**What:** `PATCH /api/v2/species/{id}/` accepts any subset of the create
payload's fields; `null` means "leave unchanged" and `tags` replaces the whole
set.
**Why:** Adding tags was the trigger, but `species_create` already owns the
validation and camelCase error remapping (now the shared
`_species_validation_errors` helper), so covering every admin-editable field
cost little more than tags alone would have.
**Rejected:** A tags-only endpoint - it would have needed a sibling endpoint for
the first vernacular-name fix. Append-only tag semantics were rejected too:
replacement matches create, and leaves removal possible.

## 2026-08-26 - Dataset names come from the GBIF registry, after the transaction

**What:** Restored the registry lookup that names datasets whose download
carries an empty `dwc:datasetName`; it now runs after the import transaction
commits, and an empty incoming name no longer overwrites a stored one.
**Why:** The workaround for issue #41 was commented out during a GBIF outage and
then deleted outright by the `run_import` refactor, leaving 236 of 272 datasets
unnamed on the OneSTOP instance; naming is cosmetic, so it must not be able to
hold a write transaction open or roll a good import back.
**Rejected:** Doing the lookup inside the transaction, where the old hack lived -
zero blank-name window, but hundreds of blocking HTTP calls on the import's
critical path.

## 2026-09-01 - Filter id lists get a compact query-string encoding

**What:** `speciesIds` and the other id filters now travel as one comma/range
value (`speciesIds=1-350,402`) on the API, the tile endpoints and the index-page
address bar; the repeated-parameter spelling is still accepted everywhere.
**Why:** An alert selecting a few hundred species produced a ~7 KB request line
on every observation and map-tile request, past gunicorn's 4094-byte default, so
the alert page was simply broken on such an instance.
**Rejected:** Sending an `alertId` the server expands - a constant-size URL and
a tighter fit for the reported case, but no help to a visitor who hand-picks the
same species on the index page. Also rejected: raising the gunicorn limit alone,
which moves the ceiling instead of shrinking the request (the limit was raised
too, but as headroom).

## 2026-09-02 - Custom CSS follows PrimeVue semantic tokens instead of fixed colors

**What:** `body` and the map/dialog panels now take their colors from
`--p-text-color` / `--p-content-*` / `--p-highlight-*` rather than hardcoded
values, so the app is readable under `prefers-color-scheme: dark`; sidebar muted
text moved slate-500 -> slate-400 and the green/amber toggle states one shade
darker to clear WCAG AA.
**Why:** PrimeVue's preset emits `color-scheme: dark` on `:root`, which makes the
browser paint the canvas black, while our CSS still declared light-mode colors -
page-fragment text, D3 axis labels and the white map panels became unreadable.
**Rejected:** Setting `darkModeSelector: false` to force the app light - one
line and it fixes the same symptom, but it throws away a dark theme PrimeVue
already renders correctly. Also rejected: a parallel
`@media (prefers-color-scheme: dark)` block of our own, which would duplicate
PrimeVue's switch and drift from it.
