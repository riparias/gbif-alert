# DwCA read-path benchmarks

Benchmarks for the Darwin Core Archive (DwCA) read path used by
`import_observations` (python-dwca-reader 0.16.4 -> 0.17.1, plus the switch
from the row-object API to positional `iter_terms`, plus a narrowed discovery
pass that requests 3 terms instead of building a full row).

Not part of the test suite; not run in CI. Run manually before/after changes
to the read path, back to back in one sitting on an idle machine.

## Headline finding

The DwCA parse itself got roughly **12x faster**. The full end-to-end import
only got **1.3-1.4x faster**. Parsing was never the dominant cost of an
import - inserting/updating rows in Postgres is. See "Where did the time go"
below for the stage-by-stage breakdown that shows this directly, not just as
an inference from the two ratios.

## Scripts and how to run them

All commands assume the repo root and require `PYTHONPATH=.` (a
directly-executed script under `benchmarks/` does not have the repo root on
`sys.path`, so `django.setup()` cannot import `djangoproject.settings`
otherwise).

### `bench_parse.py` - parse-only, three read-path variants

```bash
# baseline: 0.16.4, row-object path (frozen legacy adapter)
PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py <archive> rows

# upgrade: 0.17.1, same row-object path (library-only effect)
PYTHONPATH=. uv run python benchmarks/bench_parse.py <archive> rows

# iter_terms: 0.17.1, the new positional path + narrowed discovery
PYTHONPATH=. uv run python benchmarks/bench_parse.py <archive> iter_terms
```

Important: all three of these run from the **same, current checkout**. The
0.16.4 baseline point is produced by overriding only the library version with
`--with`; the old row-based reading logic itself lives on in this checkout as
a frozen copy (`dashboard/tests/commands/legacy_dwca_adapter.py`) so it stays
measurable without needing the pre-upgrade commit. `bench_parse.py` measures
three points per variant: open archive, discovery pass (dataset keys / basis
of record), and a full pass building every `RawObservationRow`.

### `bench_e2e.py` - end-to-end import (parse + database writes)

```bash
PYTHONPATH=. uv run python benchmarks/bench_e2e.py <archive.zip>

# baseline, for comparison - here the OLD IMPORTER CODE must run, not just
# the old library, so this only works from a checkout of the pre-upgrade
# commit (see "Baseline setup" below):
PYTHONPATH=. uv run python benchmarks/bench_e2e.py <archive.zip> --dwca-version 0.16.4
```

Restores `gbif_alert_bench` from `gbif_alert_bench_template` before every
run, then runs `manage.py import_observations` as a child process and times
it. Refuses to run unless the resolved database name contains `"bench"`.

### Baseline setup (`bench_e2e.py` "before" side only)

The current checkout calls `iter_terms`, which does not exist in 0.16.4, so
pinning the library version alone crashes it. The end-to-end "before" point
therefore needs a checkout of the commit before the upgrade, with the
benchmark harness copied in:

```bash
BASE=<commit before "Upgrade python-dwca-reader to 0.17.1">
git worktree add /tmp/gbif-baseline "$BASE"
cp -R benchmarks /tmp/gbif-baseline/     # benchmarks/ does not exist at BASE
cd /tmp/gbif-baseline
PYTHONPATH=. uv run python benchmarks/bench_e2e.py <archive> --dwca-version 0.16.4
```

`bench_e2e.py` restores the database via `psql` with absolute database names,
so it works identically from a worktree.

### `make_subset.py` / `setup_bench_db.py` / `check_equivalence.py`

Supporting scripts used to build the 100K archive, seed the bench database
from the archive's own taxon keys, and verify the `iter_terms` adapter
against the frozen row adapter row-by-row. Not re-run for this benchmark;
see their own docstrings.

## Methodology

- All configurations were measured back to back, in one sitting, on an
  otherwise idle machine.
- Each configuration was run **at least twice**; a pair is required to agree
  within roughly 5% before being reported as the comparable figure. Every
  run, including any discarded as an outlier, is listed below in full - none
  are silently dropped.
- **Ratios are the result. Absolute seconds are context only** - they depend
  on this specific machine, disk, and Postgres instance.
- `peak=` / `peak RSS` is a process-wide high-water mark: it never decreases
  within a run, so it is comparable **across invocations** of a script
  (e.g. baseline peak vs upgrade peak) but **not across the lines of one
  invocation** (a later line's peak includes everything before it).
- One configuration - the 0.16.4 parse-only baseline - showed a cold-cache
  outlier on its first run at 1M scale (and arguably at 100K scale too for
  the end-to-end baseline). Where that happened, the first run is reported
  explicitly as an outlier and excluded from the ratio, and a third run was
  taken to confirm agreement between the remaining two. See "Cold-cache
  outliers" below.

## Machine, OS, Python, commit

- Machine: Apple M2 Max (macOS), 2026-07-29
- OS: macOS 26.5 (build 25F71)
- Python: 3.13.7 (project pin: `requires-python = ">=3.13"`)
- Commit measured (the "upgrade"/"after" side, and the current checkout for
  all parse-only points): `2c14ecac72fc5582d33ff47efcd1dfa2c9e38258` on
  branch `feature/dwca-reader-performance`
  ("Add the end-to-end import benchmark harness")
- Commit measured (the end-to-end "before" side, old importer code + old
  library, checked out into `/tmp/gbif-baseline`):
  `ffbce8059fc1d5e9a176d219f406960448ebd8e0` on `main`/`devel`
  ("Merge pull request #391 from riparias/feature/observation-date-index") -
  this is the commit immediately before "Upgrade python-dwca-reader to
  0.17.1".
- python-dwca-reader versions: 0.16.4 (baseline) and 0.17.1 (upgrade,
  iter_terms).
- Archives: `/tmp/dwca-bench-100k.zip` (100,000 core data rows, head-truncated
  from the full archive - see Caveats) and
  `/Users/nnoe/Downloads/0002644-260120142942310.zip` (1,015,049 core data
  rows).

## Cold-cache outliers

Two configurations showed a first run clearly slower than the rest, in a
pattern consistent with the OS page cache (and/or Postgres shared buffers)
being cold on the first touch of a large file or a freshly-restored database:

- **1M parse-only, 0.16.4 baseline**: run 1's full pass was 147.45s; runs 2
  and 3 were 106.99s and 105.57s (1.3% apart). Run 1 is reported below but
  excluded from every ratio; the warm figure used for ratios is the average
  of runs 2 and 3.
- **100K end-to-end, 0.16.4 baseline**: run 1 was 109.4s; runs 2 and 3 were
  102.0s and 102.5s (0.5% apart). By the time this ran, the 100K archive's
  bytes had already been read repeatedly by the preceding parse-only matrix,
  so a cold *archive* is not the likely mechanism here - more plausibly, the
  two intervening 100K end-to-end "upgrade" runs (each dropping/recreating
  the bench database and writing ~99K rows) evicted relevant OS/Postgres
  cache before this baseline's first run. The mechanism is not confirmed,
  but the empirical pattern (run 1 elevated, runs 2+3 tightly agreeing) is
  the same, so it is treated the same way: run 1 excluded from the ratio,
  warm figure is the average of runs 2 and 3.

No other configuration needed a third run; all other pairs agreed within
5% on their first two runs.

## Raw output: parse-only, 100K archive

```
$ PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py /tmp/dwca-bench-100k.zip rows   # run 1
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader 0.16.4, variant rows
  open archive                                  0.61s  n=opened  peak=131MB
  discovery pass (full row built)              19.09s  n=30 datasets, 4 bor  peak=131MB
  full RawObservationRow pass                  19.00s  n=100000  peak=132MB

$ PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py /tmp/dwca-bench-100k.zip rows   # run 2
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader 0.16.4, variant rows
  open archive                                  0.63s  n=opened  peak=131MB
  discovery pass (full row built)              19.09s  n=30 datasets, 4 bor  peak=131MB
  full RawObservationRow pass                  18.96s  n=100000  peak=132MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py /tmp/dwca-bench-100k.zip rows   # run 1
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader 0.17.1, variant rows
  open archive                                  0.30s  n=opened  peak=130MB
  discovery pass (full row built)              14.09s  n=30 datasets, 4 bor  peak=130MB
  full RawObservationRow pass                  14.10s  n=100000  peak=131MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py /tmp/dwca-bench-100k.zip rows   # run 2
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader 0.17.1, variant rows
  open archive                                  0.31s  n=opened  peak=131MB
  discovery pass (full row built)              14.03s  n=30 datasets, 4 bor  peak=131MB
  full RawObservationRow pass                  14.05s  n=100000  peak=131MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py /tmp/dwca-bench-100k.zip iter_terms   # run 1
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader 0.17.1, variant iter_terms
  open archive                                  0.28s  n=opened  peak=129MB
  discovery pass (3 terms)                      1.01s  n=30 datasets, 4 bor  peak=129MB
  full RawObservationRow pass                   1.52s  n=100000  peak=129MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py /tmp/dwca-bench-100k.zip iter_terms   # run 2
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader 0.17.1, variant iter_terms
  open archive                                  0.31s  n=opened  peak=130MB
  discovery pass (3 terms)                      1.01s  n=30 datasets, 4 bor  peak=130MB
  full RawObservationRow pass                   1.49s  n=100000  peak=130MB
```

## Raw output: parse-only, 1M archive

```
$ PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py <1M archive> rows   # run 1 - COLD CACHE, excluded from ratios
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.16.4, variant rows
  open archive                                  4.84s  n=opened  peak=136MB
  discovery pass (full row built)             146.67s  n=101 datasets, 5 bor  peak=138MB
  full RawObservationRow pass                 147.45s  n=1015049  peak=138MB

$ PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py <1M archive> rows   # run 2 - warm
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.16.4, variant rows
  open archive                                  3.96s  n=opened  peak=152MB
  discovery pass (full row built)             114.27s  n=101 datasets, 5 bor  peak=160MB
  full RawObservationRow pass                 106.99s  n=1015049  peak=160MB

$ PYTHONPATH=. uv run --with "python-dwca-reader==0.16.4" python benchmarks/bench_parse.py <1M archive> rows   # run 3 - warm, taken to confirm run 2 vs run 1
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.16.4, variant rows
  open archive                                  3.90s  n=opened  peak=141MB
  discovery pass (full row built)             104.37s  n=101 datasets, 5 bor  peak=146MB
  full RawObservationRow pass                 105.57s  n=1015049  peak=146MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py <1M archive> rows   # run 1
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.17.1, variant rows
  open archive                                  1.35s  n=opened  peak=136MB
  discovery pass (full row built)              79.33s  n=101 datasets, 5 bor  peak=137MB
  full RawObservationRow pass                  77.24s  n=1015049  peak=137MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py <1M archive> rows   # run 2
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.17.1, variant rows
  open archive                                  1.46s  n=opened  peak=137MB
  discovery pass (full row built)              77.35s  n=101 datasets, 5 bor  peak=138MB
  full RawObservationRow pass                  77.20s  n=1015049  peak=138MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py <1M archive> iter_terms   # run 1
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.17.1, variant iter_terms
  open archive                                  1.48s  n=opened  peak=137MB
  discovery pass (3 terms)                      6.44s  n=101 datasets, 5 bor  peak=138MB
  full RawObservationRow pass                   8.91s  n=1015049  peak=138MB

$ PYTHONPATH=. uv run python benchmarks/bench_parse.py <1M archive> iter_terms   # run 2
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader 0.17.1, variant iter_terms
  open archive                                  1.69s  n=opened  peak=136MB
  discovery pass (3 terms)                      6.31s  n=101 datasets, 5 bor  peak=137MB
  full RawObservationRow pass                   8.75s  n=1015049  peak=137MB
```

## Raw output: end-to-end, 100K archive

Stage logs are condensed: repetitive per-batch lines ("Bulk size reached...",
"Bulk creation", "Migrating comments", "Creating unseen observations...")
are collapsed to one sample cycle plus a count, since the full logs run to
tens of thousands of lines of per-row progress dots and repeated per-batch
messages.

```
$ PYTHONPATH=. uv run python benchmarks/bench_e2e.py /tmp/dwca-bench-100k.zip   # upgrade run 1
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader: project pin
target database: gbif_alert_bench
restoring database from template...

total wall clock: 78.3s

stage log (condensed):
  ... [Re]importing all observations -> Opening DWCA to read metadata -> pre-importing
  datasets/basis-of-record -> creating a hash table of species -> Importing all rows ...
  ... (9 bulk-insert batch cycles: Bulk size reached / Bulk creation / Migrating comments /
  Creating unseen observations, repeating) ...
  All observations imported -> migrating unseen -> deleting previous observations ->
  refreshing materialized views -> committing transaction -> vacuum analyze ->
  Import observations process successfully completed in 1m 16s

$ PYTHONPATH=. uv run python benchmarks/bench_e2e.py /tmp/dwca-bench-100k.zip   # upgrade run 2
total wall clock: 80.1s
(same stage structure as run 1)

$ cd /tmp/gbif-baseline && PYTHONPATH=. uv run python benchmarks/bench_e2e.py /tmp/dwca-bench-100k.zip --dwca-version 0.16.4   # baseline run 1 - COLD, excluded
total wall clock: 109.4s

$ cd /tmp/gbif-baseline && PYTHONPATH=. uv run python benchmarks/bench_e2e.py /tmp/dwca-bench-100k.zip --dwca-version 0.16.4   # baseline run 2 - warm
total wall clock: 102.0s

$ cd /tmp/gbif-baseline && PYTHONPATH=. uv run python benchmarks/bench_e2e.py /tmp/dwca-bench-100k.zip --dwca-version 0.16.4   # baseline run 3 - warm, confirms run 2
total wall clock: 102.5s
```

Full condensed stage log, upgrade run 1 (representative; baseline run has the
same structure with the row-based, unnarrowed discovery pass and slower
per-batch timings):

```
archive: /tmp/dwca-bench-100k.zip
python-dwca-reader: project pin
target database: gbif_alert_bench
restoring database from template...

total wall clock: 78.3s

stage log (repetitive per-batch lines collapsed):
  Wed Jul 29 13:45:46 2026: (Re)importing all observations [peak RSS: 135 MB]
  Wed Jul 29 13:45:46 2026: Using a user-provided DWCA file [peak RSS: 136 MB]
  Wed Jul 29 13:45:46 2026: Opening DWCA to read metadata (this also builds the line-offset index) [peak RSS: 136 MB]
  Wed Jul 29 13:45:46 2026: GBIF download id read from DWCA metadata: 0002644-260120142942310 [peak RSS: 146 MB]
  Wed Jul 29 13:45:46 2026: Real import is starting. We'll use a transaction and put the website in maintenance mode [peak RSS: 146 MB]
  Wed Jul 29 13:45:46 2026: Created a new DataImport object: #1 [peak RSS: 146 MB]
  Wed Jul 29 13:45:46 2026: 3. Pre-importing all datasets and basis of record values [peak RSS: 146 MB]
  Wed Jul 29 13:45:46 2026: 3.1 Scanning rows to get the dataset keys and basis of record values [peak RSS: 146 MB]
  Wed Jul 29 13:45:47 2026: 3.3 Creating/updating the Dataset objects [peak RSS: 156 MB]
  [30 lines like 'Creating/updating dataset <uuid>' elided]
  Wed Jul 29 13:45:47 2026: 3.4 Creating/getting the BasisOfRecord objects [peak RSS: 156 MB]
  Wed Jul 29 13:45:47 2026: 4. Creating a hash table of species [peak RSS: 156 MB]
  Wed Jul 29 13:45:47 2026: 5. Building verification status hash [peak RSS: 156 MB]
  Wed Jul 29 13:45:47 2026: Importing all rows [peak RSS: 163 MB]
  Wed Jul 29 13:45:52 2026: Bulk size reached... [peak RSS: 187 MB]
  Wed Jul 29 13:45:52 2026: Bulk creation [peak RSS: 187 MB]
  Wed Jul 29 13:45:54 2026: Migrating comments [peak RSS: 297 MB]
  Wed Jul 29 13:45:54 2026: Creating unseen observations for new observations [peak RSS: 297 MB]
  ... (9 more bulk-insert batch cycles like the one above, same 4 messages repeating) ...
  Wed Jul 29 13:46:59 2026: All observations imported [peak RSS: 300 MB]
  Wed Jul 29 13:46:59 2026: Migrating unseen observations [peak RSS: 300 MB]
  Wed Jul 29 13:46:59 2026: now deleting observations linked to previous data imports... [peak RSS: 300 MB]
  Wed Jul 29 13:46:59 2026: Previous observations deleted [peak RSS: 300 MB]
  Wed Jul 29 13:46:59 2026: We'll now create or refresh the materialized views. This can take a while. [peak RSS: 300 MB]
  Wed Jul 29 13:47:00 2026: Deleting (no longer used) dataset  [peak RSS: 300 MB]
  Wed Jul 29 13:47:00 2026: Deleting (no longer used) dataset  [peak RSS: 300 MB]
  Wed Jul 29 13:47:00 2026: Updating the DataImport object [peak RSS: 300 MB]
  Wed Jul 29 13:47:00 2026: Committing the transaction [peak RSS: 300 MB]
  Wed Jul 29 13:47:01 2026: Transaction committed [peak RSS: 300 MB]
  Wed Jul 29 13:47:01 2026: Leaving maintenance mode. [peak RSS: 300 MB]
  Wed Jul 29 13:47:01 2026: Vacuuming and analyzing the rewritten tables [peak RSS: 300 MB]
  Wed Jul 29 13:47:02 2026: VACUUM ANALYZE done on dashboard_observation [peak RSS: 300 MB]
  Wed Jul 29 13:47:02 2026: VACUUM ANALYZE done on dashboard_observationunseen [peak RSS: 300 MB]
  Wed Jul 29 13:47:02 2026: Sending success report [peak RSS: 300 MB]
  Wed Jul 29 13:47:02 2026: Import observations process successfully completed in 1m 16s [peak RSS: 300 MB]
```

## Raw output: end-to-end, 1M archive

Both sides sanity-checked: `dashboard_observation` count after the final run
was 1,010,445 out of 1,015,049 core rows (99.55% imported, 0.45% skipped) -
consistent with the bench database's 100% taxon-key coverage (see Caveats).
No run reported `IMPORT FAILED` or mass skips.

```
$ cd /tmp/gbif-baseline && PYTHONPATH=. uv run python benchmarks/bench_e2e.py <1M archive> --dwca-version 0.16.4   # baseline run 1
total wall clock: 861.0s   (14m 19s reported by the importer itself)

$ cd /tmp/gbif-baseline && PYTHONPATH=. uv run python benchmarks/bench_e2e.py <1M archive> --dwca-version 0.16.4   # baseline run 2
total wall clock: 883.7s   (14m 42s)

$ PYTHONPATH=. uv run python benchmarks/bench_e2e.py <1M archive>   # upgrade run 1
total wall clock: 610.5s   (10m 7s)

$ PYTHONPATH=. uv run python benchmarks/bench_e2e.py <1M archive>   # upgrade run 2
total wall clock: 603.4s   (10m 2s)
```

Both baseline runs agree within 2.6%; both upgrade runs agree within 1.2%.
Neither pair needed a third run.

Full condensed stage log, baseline run 1 (repetitive per-batch and per-dataset
lines collapsed - the full archive has 101 datasets and ~101 bulk-insert
batches):

```
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader: 0.16.4
target database: gbif_alert_bench
restoring database from template...

total wall clock: 861.0s

stage log (repetitive per-item lines collapsed, see note):
  Wed Jul 29 14:22:28 2026: (Re)importing all observations [peak RSS: 140 MB]
  Wed Jul 29 14:22:28 2026: Using a user-provided DWCA file [peak RSS: 141 MB]
  Wed Jul 29 14:22:28 2026: Opening DWCA to read metadata (this also builds the line-offset index) [peak RSS: 141 MB]
  Wed Jul 29 14:22:31 2026: GBIF download id read from DWCA metadata: 0002644-260120142942310 [peak RSS: 157 MB]
  Wed Jul 29 14:22:31 2026: Real import is starting. We'll use a transaction and put the website in maintenance mode [peak RSS: 157 MB]
  Wed Jul 29 14:22:31 2026: Created a new DataImport object: #1 [peak RSS: 157 MB]
  Wed Jul 29 14:22:31 2026: 3. Pre-importing all datasets and basis of record values [peak RSS: 157 MB]
  Wed Jul 29 14:22:31 2026: 3.1 Scanning rows to get the dataset keys and basis of record values [peak RSS: 157 MB]
  Wed Jul 29 14:24:16 2026: 3.3 Creating/updating the Dataset objects [peak RSS: 171 MB]
  [101 lines like 'Creating/updating dataset <uuid>' / 'Deleting (no longer used) dataset <name>' elided]
  Wed Jul 29 14:24:16 2026: 3.4 Creating/getting the BasisOfRecord objects [peak RSS: 171 MB]
  Wed Jul 29 14:24:16 2026: 4. Creating a hash table of species [peak RSS: 171 MB]
  Wed Jul 29 14:24:16 2026: 5. Building verification status hash [peak RSS: 171 MB]
  Wed Jul 29 14:24:16 2026: Importing all rows [peak RSS: 171 MB]
  Wed Jul 29 14:24:25 2026: Bulk size reached... [peak RSS: 187 MB]
  Wed Jul 29 14:24:25 2026: Bulk creation [peak RSS: 187 MB]
  Wed Jul 29 14:24:26 2026: Migrating comments [peak RSS: 296 MB]
  Wed Jul 29 14:24:26 2026: Creating unseen observations for new observations [peak RSS: 296 MB]
  ... (101 bulk-insert batch cycles total in this run, same 4 messages repeating) ...
  Wed Jul 29 14:36:29 2026: All observations imported [peak RSS: 307 MB]
  Wed Jul 29 14:36:29 2026: Migrating unseen observations [peak RSS: 307 MB]
  Wed Jul 29 14:36:29 2026: now deleting observations linked to previous data imports... [peak RSS: 307 MB]
  Wed Jul 29 14:36:29 2026: Previous observations deleted [peak RSS: 307 MB]
  Wed Jul 29 14:36:29 2026: We'll now create or refresh the materialized views. This can take a while. [peak RSS: 307 MB]
  [7 lines like 'Creating/updating dataset <uuid>' / 'Deleting (no longer used) dataset <name>' elided]
  Wed Jul 29 14:36:34 2026: Deleting (no longer used) basis of record LIVING_SPECIMEN [peak RSS: 307 MB]
  Wed Jul 29 14:36:34 2026: Updating the DataImport object [peak RSS: 307 MB]
  Wed Jul 29 14:36:35 2026: Committing the transaction [peak RSS: 307 MB]
  Wed Jul 29 14:36:47 2026: Transaction committed [peak RSS: 307 MB]
  Wed Jul 29 14:36:47 2026: Leaving maintenance mode. [peak RSS: 307 MB]
  Wed Jul 29 14:36:47 2026: Vacuuming and analyzing the rewritten tables [peak RSS: 307 MB]
  Wed Jul 29 14:36:48 2026: VACUUM ANALYZE done on dashboard_observation [peak RSS: 307 MB]
  Wed Jul 29 14:36:48 2026: VACUUM ANALYZE done on dashboard_observationunseen [peak RSS: 307 MB]
  Wed Jul 29 14:36:48 2026: Sending success report [peak RSS: 307 MB]
  Wed Jul 29 14:36:48 2026: Import observations process successfully completed in 14m 19s [peak RSS: 307 MB]
```

Full condensed stage log, upgrade run 1:

```
archive: /Users/nnoe/Downloads/0002644-260120142942310.zip
python-dwca-reader: project pin
target database: gbif_alert_bench
restoring database from template...

total wall clock: 610.5s

stage log (repetitive per-item lines collapsed, see note):
  Wed Jul 29 14:51:37 2026: (Re)importing all observations [peak RSS: 151 MB]
  Wed Jul 29 14:51:37 2026: Using a user-provided DWCA file [peak RSS: 151 MB]
  Wed Jul 29 14:51:37 2026: Opening DWCA to read metadata (this also builds the line-offset index) [peak RSS: 151 MB]
  Wed Jul 29 14:51:39 2026: GBIF download id read from DWCA metadata: 0002644-260120142942310 [peak RSS: 162 MB]
  Wed Jul 29 14:51:39 2026: Real import is starting. We'll use a transaction and put the website in maintenance mode [peak RSS: 162 MB]
  Wed Jul 29 14:51:39 2026: Created a new DataImport object: #1 [peak RSS: 162 MB]
  Wed Jul 29 14:51:39 2026: 3. Pre-importing all datasets and basis of record values [peak RSS: 162 MB]
  Wed Jul 29 14:51:39 2026: 3.1 Scanning rows to get the dataset keys and basis of record values [peak RSS: 162 MB]
  Wed Jul 29 14:51:46 2026: 3.3 Creating/updating the Dataset objects [peak RSS: 172 MB]
  [101 lines like 'Creating/updating dataset <uuid>' / 'Deleting (no longer used) dataset <name>' elided]
  Wed Jul 29 14:51:46 2026: 3.4 Creating/getting the BasisOfRecord objects [peak RSS: 172 MB]
  Wed Jul 29 14:51:46 2026: 4. Creating a hash table of species [peak RSS: 172 MB]
  Wed Jul 29 14:51:46 2026: 5. Building verification status hash [peak RSS: 172 MB]
  Wed Jul 29 14:51:46 2026: Importing all rows [peak RSS: 172 MB]
  Wed Jul 29 14:51:51 2026: Bulk size reached... [peak RSS: 179 MB]
  Wed Jul 29 14:51:51 2026: Bulk creation [peak RSS: 179 MB]
  Wed Jul 29 14:51:53 2026: Migrating comments [peak RSS: 287 MB]
  Wed Jul 29 14:51:53 2026: Creating unseen observations for new observations [peak RSS: 287 MB]
  ... (101 bulk-insert batch cycles total in this run, same 4 messages repeating) ...
  Wed Jul 29 15:01:26 2026: All observations imported [peak RSS: 312 MB]
  Wed Jul 29 15:01:26 2026: Migrating unseen observations [peak RSS: 312 MB]
  Wed Jul 29 15:01:26 2026: now deleting observations linked to previous data imports... [peak RSS: 312 MB]
  Wed Jul 29 15:01:26 2026: Previous observations deleted [peak RSS: 312 MB]
  Wed Jul 29 15:01:26 2026: We'll now create or refresh the materialized views. This can take a while. [peak RSS: 312 MB]
  [7 lines like 'Creating/updating dataset <uuid>' / 'Deleting (no longer used) dataset <name>' elided]
  Wed Jul 29 15:01:31 2026: Deleting (no longer used) basis of record LIVING_SPECIMEN [peak RSS: 312 MB]
  Wed Jul 29 15:01:31 2026: Updating the DataImport object [peak RSS: 312 MB]
  Wed Jul 29 15:01:32 2026: Committing the transaction [peak RSS: 312 MB]
  Wed Jul 29 15:01:43 2026: Transaction committed [peak RSS: 312 MB]
  Wed Jul 29 15:01:43 2026: Leaving maintenance mode. [peak RSS: 312 MB]
  Wed Jul 29 15:01:43 2026: Vacuuming and analyzing the rewritten tables [peak RSS: 312 MB]
  Wed Jul 29 15:01:44 2026: VACUUM ANALYZE done on dashboard_observation [peak RSS: 312 MB]
  Wed Jul 29 15:01:44 2026: VACUUM ANALYZE done on dashboard_observationunseen [peak RSS: 312 MB]
  Wed Jul 29 15:01:44 2026: Sending success report [peak RSS: 312 MB]
  Wed Jul 29 15:01:44 2026: Import observations process successfully completed in 10m 7s [peak RSS: 312 MB]
```

## Ratio table

Figures are the mean of the warm/comparable runs listed above (cold-cache
run 1's are excluded where flagged). "e2e total" has only a baseline ->
upgrade column: `bench_e2e.py` measures exactly two points (old code + old
library vs new code + new library), not an intermediate "library-only,
new e2e" variant.

### 100K archive

| stage      | baseline -> upgrade | upgrade -> iter_terms | baseline -> iter_terms |
|------------|---------------------|------------------------|--------------------------|
| open       | 0.62s -> 0.31s = 2.03x | 0.31s -> 0.30s = 1.03x | 0.62s -> 0.30s = 2.10x |
| discovery  | 19.09s -> 14.06s = 1.36x | 14.06s -> 1.01s = 13.92x | 19.09s -> 1.01s = 18.90x |
| full pass  | 18.98s -> 14.08s = 1.35x | 14.08s -> 1.51s = 9.35x | 18.98s -> 1.51s = 12.61x |
| e2e total  | 102.25s -> 79.2s = 1.29x | n/a | n/a |

### 1M archive

| stage      | baseline -> upgrade | upgrade -> iter_terms | baseline -> iter_terms |
|------------|---------------------|------------------------|--------------------------|
| open       | 3.93s -> 1.41s = 2.79x | 1.41s -> 1.59s = 0.89x (see note) | 3.93s -> 1.59s = 2.48x |
| discovery  | 109.32s -> 78.34s = 1.40x | 78.34s -> 6.38s = 12.29x | 109.32s -> 6.38s = 17.15x |
| full pass  | 106.28s -> 77.22s = 1.38x | 77.22s -> 8.83s = 8.75x | 106.28s -> 8.83s = 12.03x |
| e2e total  | 872.35s -> 606.95s = 1.44x | n/a | n/a |

Note on 1M "open" upgrade -> iter_terms: iter_terms open (1.59s avg) came out
*slower* than plain-rows open (1.41s avg) at this scale, a ~13% difference
inside numbers this small (under 2s) and likely just process/OS noise at
that magnitude rather than a real effect - flagging rather than smoothing it
away. It has no bearing on the full-pass numbers, which are an order of
magnitude larger and agree tightly run-to-run.

Cross-scale corroboration for the warm-baseline treatment: the 100K and 1M
full-pass baseline -> iter_terms ratios are 12.61x and 12.03x - close to each
other despite the 10x difference in row count, which is what you'd expect if
both are measuring the same effect and the 1M baseline's run 1 really was a
cache artifact rather than the "true" number.

### Library upgrade alone (0.16.4 -> 0.17.1, same row-based code)

The baseline -> upgrade column above, on the row path, is the effect of
*only* bumping the library version with the pre-existing row-object code
unchanged: **1.35x at 100K, 1.38x at 1M**. This is measured, not estimated.

This is well short of the ~4x python-dwca-reader's own upstream benchmarks
report for the 0.16 -> 0.17 jump. A plausible but **unconfirmed** explanation:
this archive's `occurrence.txt` has 230 columns (verified: `unzip -p
dwca-bench-100k.zip occurrence.txt | head -1 | tr '\t' '\n' | wc -l` -> 230),
where upstream's benchmark used roughly 50. The row path materializes a full
column dict either way, on both library versions, so a wider row leaves less
headroom for the iteration rewrite alone to remove - the bulk of this
archive's win instead comes from switching to `iter_terms` (only requesting
the ~10-20 columns actually used) plus the narrowed discovery pass, not from
the library bump by itself. This is a hypothesis, not a confirmed cause.

## Where did the time go (1M end-to-end, stage breakdown)

Derived from the timestamped stage log of representative runs (baseline
run 1, upgrade run 1 - see raw output above), not from the `bench_parse.py`
figures, so this is an independent check on the headline finding:

| stage                                              | baseline (0.16.4, old code) | upgrade (0.17.1, iter_terms) | change |
|-----------------------------------------------------|------------------------------|-------------------------------|--------|
| open + read metadata                                 | ~3s   | ~2s   | roughly flat |
| discovery ("3.1 Scanning rows...")                    | ~105s | ~7s   | -98s (matches the parse-only discovery ratio, ~15x) |
| dataset/basis-of-record creation                      | <1s   | <1s   | flat |
| **"Importing all rows" (parse full pass + DB writes)** | **~733s** | **~580s** | **-153s, only 1.26x** |
| tail (unseen migration, cleanup, materialized views, vacuum) | ~19s | ~18s | roughly flat |
| **total**                                              | **~861s** | **~607s** | **-254s, 1.42x** |

The "Importing all rows" stage is where parsing and database writes both
happen, and it dominates the total (85%+ of wall clock on both sides). Within
that stage, the parse-only benchmark says the parse itself shrank from
~106s to ~9s (a ~97s saving) - almost exactly matching the ~98s saved in the
discovery stage above, which uses the same read APIs. But the *stage's*
total time only dropped by ~153s (733s -> 580s), meaning roughly 570-630s of
that stage on both sides is Postgres work (bulk inserts, comment migration,
unseen-observation creation) that the DwCA read-path change does not touch
at all. That is the direct, stage-level evidence for the headline finding:
parsing was never the dominant cost of an import.

## Caveats

- The 1M archive (`/Users/nnoe/Downloads/0002644-260120142942310.zip`) has
  1,015,049 core data rows (not 1,015,050 - that figure came from `wc -l`,
  which counts the header line).
- The 100K archive (`/tmp/dwca-bench-100k.zip`) is **head-truncated**, not
  sampled: it is the first 100,000 core rows of the full archive, so its
  dataset composition differs from the full archive (GBIF exports are
  grouped by dataset). Measured impact on scanned bytes is under 1% (see
  Task 9 notes); this does not affect the parse-only ratios materially, and
  the cross-scale corroboration above (12.61x at 100K vs 12.03x at 1M) is
  itself evidence the truncation is not distorting the comparison.
- The archive predates the COL taxonomy migration, so its `taxonKey` values
  do not match any real current species. The end-to-end benchmark database is
  seeded with **synthetic species created directly from the archive's own
  top taxon keys** (155 distinct taxon keys found, all 155 seeded, giving
  100% row coverage: 1,015,049 / 1,015,049 rows match a seeded species).
  Production has real species with real GBIF/COL taxon keys and will skip
  many more incoming rows than this benchmark does.
- Because skipped rows do strictly **less** work than imported rows (no
  object construction, no bulk insert, no comment migration, no unseen-row
  creation), a production import with a realistic skip rate would spend
  proportionally *less* time in the part of the pipeline this change
  speeds up relative to the parts it doesn't touch. The measured end-to-end
  gain here (1.29x-1.44x) is therefore a conservative estimate, not an
  inflated one, relative to a production-like skip rate.
- Both end-to-end sides were sanity-checked against row counts: after the
  final run, `dashboard_observation` held 1,010,445 rows (99.55% of
  1,015,049), consistent with the near-100% taxon coverage above. No run
  reported `IMPORT FAILED` or mass skips.
- A concurrent, unrelated Claude Code session briefly checked out a
  different branch in the main repository checkout during this benchmark
  run. All actual measurements were re-run afterward from isolated git
  worktrees (`/tmp/gbif-baseline`, `/tmp/gbif-upgrade`) once this was
  discovered, so no reported figure was collected while that interference
  was active. Noted here for full transparency, not because it is believed
  to have affected any number in this file.
