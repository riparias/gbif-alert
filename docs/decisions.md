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
