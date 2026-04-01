# Frontend Migration Plan

## Goal

Migrate the gbif-alert frontend from the current hybrid Django/Vue (Webpack, Bootstrap,
Options API) setup to a modern stack (Vite, PrimeVue, Composition API, Vue Router, Pinia,
Django Ninja) - incrementally, on main, with no long-running branches or parallel URLs.

## Architecture Decisions

| Decision              | Choice                         | Rationale                                                        |
|-----------------------|--------------------------------|------------------------------------------------------------------|
| Bundler               | Vite + django-vite             | HMR, fast builds, simpler config than Webpack                    |
| UI framework          | PrimeVue (Aura preset)        | Rich components (DataTable, etc.), modern look, less custom code |
| Component style       | `<script setup lang="ts">`    | Concise, better TypeScript inference                             |
| State management      | Pinia                          | Shared filter state, survives route changes                      |
| Routing               | Vue Router (history mode)      | Client-side nav for core pages, solves filter-loss problem; Django catch-all serves the SPA shell for any unmatched path |
| API layer             | Django Ninja (incremental)     | Type-safe, auto OpenAPI, lightweight                             |
| TypeScript types      | openapi-typescript from spec   | End-to-end type safety, no manual interfaces.ts sync             |
| E2E testing           | Playwright + pytest-playwright | Fast, multi-browser, native Django integration                   |
| CSS                   | PrimeVue theme + minimal utils | Replace Bootstrap progressively                                  |
| Maps                  | OpenLayers (keep as-is)        | Wrap existing components, refactor to Composition API only       |
| Deployment            | Vite build step before collectstatic | Works for current VPS and future ECS                        |

## Migration Strategy: Page-by-Page on Main

The key principle: **every commit on main is shippable**. No feature flags, no long-running
branches.

Vite and Webpack coexist during the migration. Old pages load the Webpack bundle. New pages
load the Vite bundle. The shared navbar/footer (PrimeVue) is in the Vite bundle and mounted
on all pages (old and new) from the start.

During active page migration work (Phase 2+), a temporary `/new/` Django route serves the
in-progress Vue page. This is not user-facing (not in the navbar, not linked) - it exists
solely to give visual feedback during development. It is removed when the real routing swap
happens. This keeps the existing page untouched and shippable throughout.

## Phases

### Phase 0: Infrastructure Setup

Set up the new toolchain alongside the existing one. No user-visible changes.

- [x] 0.1 - Install Vite, configure `vite.config.ts` for Django integration
- [x] 0.2 - Install and configure `django-vite` (manifest mode for production,
        dev server proxy for development)
- [x] 0.3 - Install PrimeVue, Pinia, Vue Router
- [x] 0.4 - Create new entry point (`assets/new-frontend/main.ts`) with Vue app,
        router, Pinia store, PrimeVue plugin, i18n
- [x] 0.5 - Set up the project structure (see below)
- [x] 0.6 - Verify: Vite dev server runs, production build works, django-vite
        injects assets into a test template, Webpack still works unchanged
- [x] 0.7 - Install Django Ninja, create a minimal `/api/v2/` router (empty for now)
- [x] 0.8 - Install Playwright, configure pytest-playwright, write one smoke test
        (page loads, no JS errors)

**Project structure** (new files, existing files stay where they are):

```
assets/
  new-frontend/           # <-- new Vite-managed frontend
    main.ts               # Vue app bootstrap
    App.vue               # Root component (navbar, footer, <router-view>)
    router/
      index.ts            # Vue Router config
    stores/
      filters.ts          # Pinia store for dashboard filters
      user.ts             # Pinia store for current user
    components/
      layout/
        NavBar.vue
        FooterBar.vue
      ...                 # Migrated/new components go here
    pages/
      IndexPage.vue
      ObservationDetailPage.vue
      AlertDetailPage.vue
      ...
    composables/          # Shared composition functions
      useApi.ts           # Typed API client (wraps axios or fetch)
    utils/
      csrf.ts             # getCsrf() helper (reads csrftoken cookie)
    types/                # Auto-generated from OpenAPI (later)
  ts/                     # <-- existing Webpack-managed frontend (untouched)
    early_alert.ts
    components/
    ...
```

### Phase 1: Shared Layout (Navbar + Footer)

First user-visible change. All pages get the new look simultaneously.

- [x] 1.1 - Build `NavBar.vue` with PrimeVue Menubar, including language selector and
        user dropdown. FooterBar deferred: footer stays as Django HTML for now
        (the `footer_left_col` page fragment contains arbitrary admin HTML that would
        need `v-html`; not worth the complexity until Phase 2 Bootstrap cleanup).
- [x] 1.2 - Update `base.html`: inject `nav_config_json` as
        `<script type="application/json" id="gbif-alert-nav-config">`, move
        `#new-frontend` to top of body (before page content), remove old
        `_navbar.html` include.
- [x] 1.3 - Removed old Bootstrap navbar from `base.html`. Footer kept as Django
        template (see 1.1 note above).
- [x] 1.4 - Verify all existing pages still work with the new layout
- [x] 1.5 - Write Playwright tests for navbar navigation (7 tests in
        `dashboard/tests/playwright/test_navbar.py`; Django unit tests for `nav_config_json`
        in `dashboard/tests/views/test_pages.py::NavConfigJsonTests`; Selenium tests
        updated to work with the new navbar)

**Open TODO tracked in `NavBar.vue`**:
- Active page detection: currently uses `window.location.pathname`. Replace with
  `useRoute().path` once all pages are Vue routes (Phase 3+).

**Note**: Page bodies still use Bootstrap. The visual contrast is mild since custom
CSS is minimal. Footer stays Bootstrap until Phase 2.

### Phase 2: Index Page + Observation Details

The most complex migration. Proves the full architecture. Solves the filter-loss problem.

**Strategy**: Build bottom-up behind a temporary `/new/` dev URL (see Migration Strategy
above). Ninja endpoints are created just-in-time alongside the UI component that consumes
them - not all upfront. Schemas live in `dashboard/api_v2_schemas.py`. The existing index
page is untouched until step 2.13.

- [x] 2.1 - Ninja list endpoints for filter dropdowns (species, datasets, areas,
        basis-of-record, data-imports) + Pydantic schemas in `dashboard/api_v2_schemas.py`
- [x] 2.2 - Generate TypeScript types from OpenAPI spec (`openapi-typescript`);
        `npm run generate-types` exports the schema and writes
        `assets/new-frontend/types/api.ts`; re-run after any API change
ok- [x] 2.3 - `filters` Pinia store (`assets/new-frontend/stores/filters.ts`),
        mirroring the `DashboardFilters` interface from `assets/ts/interfaces.ts`
- [x] 2.4 - Temporary `/new/` Django view + route (dev scaffold, removed in 2.13)
- [x] 2.5 - `IndexPage.vue` skeleton at `/new/` (PrimeVue layout shell, no real data)
- [x] 2.6 - Ninja paginated observations endpoint (`GET /api/v2/observations/`) +
        PrimeVue DataTable in `IndexPage.vue`
- [x] 2.7 - Filter panel (species/datasets/areas/basis-of-record dropdowns, date range,
        status, verified filter) using PrimeVue MultiSelect + DatePicker; filters
        wired to DataTable via Pinia store
- [x] 2.8 - Counter component (`ObservationCounter.vue`); reads `count` from the
        observations list response — no separate endpoint needed since
        `GET /api/v2/observations/` already returns the total count
- [x] 2.9 - Ninja monthly histogram endpoint (`GET /api/v2/observations/histogram/`) +
        `ObservationHistogram.vue` (D3 scales + Vue SVG; backend explicitly ignores
        date filters so the histogram always shows the full temporal range)
- [x] 2.10 - Filter state synced to URL query string (shareable URLs via vue-router
        query params)
- [x] 2.11 - Wrap existing OpenLayers map component in Composition API; add to
        `IndexPage.vue` (map tile endpoints are existing `/internal-api/maps/` routes,
        no new Ninja endpoints needed here)
- [x] 2.12 - `ObservationDetailPage.vue` as a Vue Router route:
  - [x] 2.12.1 - Ninja single-observation endpoint + observation info display
  - [x] 2.12.2 - Single observation map (reuse wrapped OpenLayers component from 2.11)
  - [x] 2.12.3 - Comments section
  - [x] 2.12.4 - Back navigation preserves filters (Pinia + router)
- [x] 2.13 - Django URL routing swap: `/` now served by the Vue SPA shell; catch-all
        added to `djangoproject/urls.py` (after auth/admin patterns) for Vue Router
        history mode; `/new/` dev route removed. `/observation/<id>/` intentionally
        kept on the old template until Phase 3 (alert detail page still links there).
- [x] 2.14 - Remove old `index.html` template. `observation_details.html` kept until
        Phase 3 (alert detail page still links to `/observation/<id>/`).
- [x] 2.15 - Removed `IndexPageRootComponent.vue`, `FilterSelector.vue`,
        `FilterSelectorModal.vue`, `FilterSelectorModalEntries.vue` from `assets/ts/`.
        `Selector.vue`, `RangeSlider.vue` and all components used by
        `AlertDetailsPageRootComponent` kept (still needed by old pages).
- [x] 2.16 - Playwright tests for index page: counter reflects DB, species filter
        narrows results, table view shows species name, row click opens drawer,
        filter state preserved when drawer closed (key migration goal).

### Phase 3: Alert CRUD

- [x] 3.1 - Django Ninja endpoints for alert operations (create, read, update, delete,
        load-as-filters, suggest-name, available-intervals)
- [x] 3.2 - Migrate `AlertDetailPage.vue` (with delete confirmation via PrimeVue
        ConfirmDialog); `ObservationsView.vue` extracted from `IndexPage` and shared
- [x] 3.3 - Migrate `AlertFormPage.vue` (create + edit); uses `SpeciesFilterModal`,
        `AreaFilterModal`, `DatasetFilterModal` — same selectors as the index page
- [x] 3.4 - Migrate `UserAlertsPage.vue` (alert list with delete buttons)
- [x] 3.5 - Add Vue Router routes, update Django URL routing
- [x] 3.6 - Remove old templates and components
        (5 Django templates + 6 Vue 2 components + alert init functions from `early_alert.ts`)
- [x] 3.7 - Playwright tests (`dashboard/tests/playwright/test_alerts.py`, 12 tests)

### Phase 4: User Areas

- [ ] 4.1 - Django Ninja endpoints for area CRUD and GeoJSON
- [ ] 4.2 - Migrate `UserAreasPage.vue` (area list, map with area polygons, draw/edit)
- [ ] 4.3 - Add Vue Router route, update Django URL routing
- [ ] 4.4 - Remove old template and UserAreasPageRootComponent
- [ ] 4.5 - Playwright tests

### Phase 5: Simple Pages + Auth

- [ ] 5.1 - Migrate About, What's New pages (can stay as Django templates with new
        layout, or become thin Vue pages - low priority either way)
- [ ] 5.2 - User Profile page (PrimeVue form components, delete account)
- [ ] 5.3 - Auth pages: evaluate whether to keep Django's built-in auth views with
        the PrimeVue layout, or rewrite as Vue pages. Django auth views are
        battle-tested - recommendation is to keep them as Django templates.

### Phase 6: Cleanup

- [ ] 6.1 - Remove Webpack config (`webpack.common.js`, `webpack.dev.js`,
        `webpack.prod.js`)
- [ ] 6.2 - Remove `assets/ts/` directory entirely
- [ ] 6.3 - Remove Bootstrap from dependencies
- [ ] 6.4 - Remove old Selenium tests
- [ ] 6.5 - Clean up `package.json` (remove webpack-related devDependencies)
- [ ] 6.6 - Update deployment scripts / CI to use `vite build` instead of
        `npm run webpack-prod`
- [ ] 6.7 - Update `base.html` to only load Vite assets
- [ ] 6.8 - Final review: no dead code, no unused dependencies

## Risks and Mitigations

| Risk                                       | Mitigation                                                  |
|--------------------------------------------|-------------------------------------------------------------|
| Bootstrap body + PrimeVue navbar looks odd | Minimal custom CSS currently; add a small bridge stylesheet  |
| OpenLayers components break during migration | Wrap first, refactor later; keep the API surface identical  |
| Django Ninja learning curve                | Start with simple endpoints, expand gradually               |
| Two bundlers in parallel slow down dev     | Temporary; Vite is fast enough that overhead is small       |
| Filter state complexity in Pinia           | Design store schema carefully in Phase 2; write unit tests  |
| i18n migration (vue-i18n stays)            | Reuse existing translation files, same library              |

## Open Questions (to resolve during implementation)

- ~~Vue Router history mode vs hash mode?~~ **Resolved: history mode.** Django catch-all
  added in step 2.13.
- PrimeVue theme customization: Aura preset out of the box, or customize colors to match
  project branding?
- ~~Should the OpenAPI -> TypeScript generation be a build step or a manual/CI step?~~
  **Resolved: manual.** Run `npm run generate-types` after API changes and commit
  `assets/new-frontend/types/api.ts`.
