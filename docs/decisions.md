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

## 2026-09-03 - Deduplicate tile output after the tile restriction, not before
**What:** The tile subquery no longer uses DISTINCT; the hexagon and min/max
endpoints count `DISTINCT id`, the point endpoint deduplicates its tile-sized
CTE, and the area parts (plus, outside parts mode, the observations) are
restricted to the tile envelope expanded by two hexagon sizes.
**Why:** DISTINCT inside the subquery blocked subquery pull-up, so every tile of
a 152k-observation alert sorted all its observations and cross-joined them with
the hexagons without an index (0.4 s -> 7 s per tile since v2.5.0, 504s once the
"Not viewed" filter no longer shrank the set).
**Rejected:** An EXISTS semi-join on the parts (25 s per tile: nothing selective
to drive it), and an observation envelope in parts mode (flips the plan to
hexagons-first, 3.4 s versus 19 ms).

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

## 2026-09-03 - Bulk-delete unseen rows in "mark all as viewed"
**What:** The job selects the ids of the matching observations that are unseen
by the user (one query through the unseen join), then deletes those rows in one
DELETE, instead of calling `mark_as_seen_by` per observation.
**Why:** One DELETE per observation ran for minutes on a 150k-observation alert,
right when the user went back to browsing it (0.16 s now for 2.6k rows).
**Rejected:** `observation__in=<queryset>` in one DELETE - invalid, the area
filter's `.extra()` names the observation table, which Django aliases in a
subquery; chunked id lists (1.5 s) and an unseen-first intersect (0.27 s), both
slower than the join.

## 2026-09-11 - Migrate comments only for replaced observations that have some
**What:** `_batch_insert_observations` asks the comment table which replaced
observations have comments (one query) and re-points only those, and resolves
the replaced rows with `values_list` instead of hydrating full models twice.
**Why:** One UPDATE per replaced observation plus 20k model instantiations per
10k-row chunk, on the full re-import path, for a handful of comments.
**Rejected:** One CASE-WHEN UPDATE mapping every old pk to its new pk - a
10k-branch statement for no gain since comments are rare.
## 2026-09-10 - Evaluate unseen rows per alert, not per user
**What:** `create_unseen_observations` runs `Alert.observations()` per alert on
the import's new observations and unions the ids per user, instead of pooling
every alert's species/datasets/basis-of-record/verified/area filters into one
query per user.
**Why:** The pooled query was a cross product (alert A's species with alert B's
dataset or area) and flagged observations matching no alert as "not viewed".
**Rejected:** A corrected OR-of-alerts pooled query - a second copy of the alert
predicate to keep in sync with the readers, for a per-import saving only.
## 2026-09-04 - Add Norwegian Bokmal (nb) as a UI language
**What:** Fourth locale wired through `LANGUAGES`, both gettext catalogs, the
Vue `translations.ts` block and the alert email; `ENABLED_LANGUAGES` default
left at `en,fr,nl` so instances opt in.
**Why:** A Norwegian team needed the tool demonstrated in their own language,
and the per-instance language machinery already made this a data-only change.
**Rejected:** the generic `no` code - Django ships no catalog for it, so the
admin and form errors would have stayed English; and scaffolding empty
catalogs, which would have shown a half-English UI during the demo.

## 2026-09-09 - Map base layers are admin-editable rows, not settings
**What:** A `MapBaseLayer` model (XYZ or WMS) editable in the Django admin,
seeded by migration with OSM HOT, ESRI Light Gray Canvas and ESRI World Imagery, and
exposed to the SPA through the existing nav-config `map` block.
**Why:** Base layers were hardcoded in the frontend, so an instance could not
offer a national WMS or drop a layer it has no rights to; the seed keeps the
upgrade free for operators who are happy with our choices.
**Rejected:** Env vars / settings (a list of records does not fit an env var,
and it would need a redeploy per change); a separate API endpoint (the nav
config already carries the map setup, and a fetch would delay the first paint);
an `is_default` flag - the first enabled layer by display order is the default,
which is one invariant less to enforce. Stamen Toner was dropped from the
defaults: Stadia Maps returns 401 for any domain not registered with them, so
it only ever loaded on localhost and alert.riparias.be; CartoDB Positron, its
first replacement, is watermarked "API KEY REQUIRED" without an account.

## 2026-09-11 - Page fragments stay unsanitized HTML
**What:** The Markdown page fragments (welcome text, news, about) keep going
through markdownify with raw HTML passthrough and into v-html on the frontend.
**Why:** Only staff write them, in the admin, and they use inline HTML on
purpose; sanitizing would strip that and add a dependency for a threat that
is already "a staff account is compromised".
**Rejected:** nh3/bleach on the API output - flagged as a defense-in-depth
option, not worth its cost today.

## 2026-09-11 - Frontend type check in CI via vue-tsc
**What:** `npm run typecheck` runs `vue-tsc --noEmit -p tsconfig.app.json` with
`skipLibCheck`, and CI runs it before the Vite build.
**Why:** Vite strips types without checking them, so 15k lines of TS/Vue had no
static check at all; the first run found two real (if harmless) errors.
**Rejected:** `tsc -b` over the project references - needs `composite` and
declaration emit for nothing, since no build consumes them; fixing the
third-party .d.ts errors instead of `skipLibCheck` - they live in node_modules
and would return with every upgrade.

## 2026-09-11 - Latest-request-wins fetching for filter-driven views
**What:** A `useLatestRequest` composable (abort previous, ignore superseded,
own loading/error) used by the observations table, histogram and species
breakdown, with an inline "could not be loaded" message and retry.
**Why:** Filter changes fired unguarded fetches; a slow earlier response (area
filters take seconds) painted over the newer one, and non-2xx responses were
silently ignored - the histogram even assigned the error body as its data.
**Rejected:** A fetch library - thirty lines cover the need and there is no
data layer to plug into; toasts for load failures - they vanish while the stale
or empty view stays. The ~25 per-action fetch sites without error feedback are
a separate follow-up (toast per action).

## 2026-09-11 - No forced vendor chunk for PrimeVue
**What:** Removed the `vendor-primevue` manualChunks rule; PrimeVue is split by
route like application code. OpenLayers, d3 and Vue keep their groupings.
**Why:** The shell imports PrimeVue's config/theme, so one forced chunk was a
static dependency of the entry and shipped every widget on every page: eager
JS 299 kB -> 191 kB gzipped, index page unchanged (it uses nearly all of it).
**Rejected:** Tuning the grouping - any single chunk the shell touches is eager
by construction; lazy-loading the map/table on the index page - a separate,
user-visible change.

## 2026-09-14 - Mark-as-viewed job takes the filter payload, not a queryset
**What:** `mark_many_observations_as_seen(filters_json, user_id)` rebuilds its
queryset through the shared `observations_for_filters` at execution time; the
endpoint enqueues `FiltersQuery.model_dump(mode="json")` and the user's pk.
**Why:** A pickled QuerySet is only valid for the Django version that produced
it (a job queued just before a deploy could fail after it), and the pickled
User carried the password hash into Redis.
**Rejected:** Keeping the queryset and accepting the rare failure - the
credential material in the queue alone justified the thirty lines.
## 2026-09-14 - Token last_used_at refreshed at most every five minutes
**What:** ApiTokenAuth only writes last_used_at when the stored value is null
or older than five minutes.
**Why:** It was a write on every authenticated request; the field is a coarse
"is this token still in use" signal on the tokens page, so minute precision
buys nothing.
**Rejected:** Dropping the field - it is the one hint that a leaked token is
being used.

## 2026-09-14 - Context-dependent empty label on the species selector
**What:** `SpeciesFilterModal` takes an `emptyLabel` prop; the alert form shows "No species selected" instead of "All species".
**Why:** an empty species selection means "all" in the explorer but is invalid for an alert, so the shared label misled users (#440).
**Rejected:** a combined "None - select at least one species" label, redundant with the hint already shown above the button.

## 2026-09-15 - Backend dependencies updated within existing caps
**What:** `uv lock --upgrade` without touching constraints: Django 5.2.17, sqlparse 0.6.0, django-ninja 1.7, django-rq 4.2, django-vite 3.2 and patch/minor updates.
**Why:** Django 5.2.16/5.2.17 and sqlparse 0.6.0 fix security issues, including a high-severity spatial lookup flaw reachable from the admin.
**Rejected:** raising the django-maintenance-mode cap to 0.23 - it changes the state value format the import relies on, for features we do not use.

## 2026-09-15 - import_observations takes a plain path for --source-dwca
**What:** dropped `argparse.FileType` for `--source-dwca`; `handle()` checks the path exists and raises `CommandError`.
**Why:** `FileType` is deprecated, left the zip open in text mode, and never ran for `call_command` callers.
**Rejected:** a custom argparse `type=` validator - `call_command` kwargs bypass `type=`, so it would not cover programmatic callers.

## 2026-09-17 - Continuous gradient legend for the hexagon map
**What:** `ObservationsMap` shows a min/max-labelled gradient legend (hidden from zoom 13) and an OL `ScaleLine`.
**Why:** the hexagon colors are a continuous log ramp over the fixed-zoom min/max, so a gradient matches them exactly.
**Rejected:** stepped color classes, which would suggest breaks the style does not have.

## 2026-09-17 - Per-dataset verified overrides, iNaturalist verified by default
**What:** `ALWAYS_VERIFIED_DATASET_KEYS` / `NEVER_VERIFIED_DATASET_KEYS` env vars force `verified` at import, bypassing the identificationVerificationStatus classification; iNaturalist research-grade is the ALWAYS default, and the detail panel says when the flag comes from an override.
**Why:** iNaturalist records reach GBIF research-grade only but without a verification status, so they were all shown as unverified (#430).
**Rejected:** writing a synthetic "research grade" status on the observation (invents source data); a hardcoded iNaturalist `if` (other instances have other such datasets).
