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

## 2026-07-28 - Species breakdown results tab
**What:** A read-only "Species" results tab, backed by a new
`/observations/species-breakdown/` aggregate endpoint.
**Why:** The sidebar reported how many species matched a search but gave no
way to find out which ones.
**Rejected:** Folding several charts behind a renamed "Chart" tab - it costs
roughly 2.5x for a chart registry serving two charts, and a pie chart is
unreadable at fifty species.
