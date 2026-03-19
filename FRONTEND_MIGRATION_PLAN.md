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
| Routing               | Vue Router (hash or history)   | Client-side nav for core pages, solves filter-loss problem       |
| API layer             | Django Ninja (incremental)     | Type-safe, auto OpenAPI, lightweight                             |
| TypeScript types      | openapi-typescript from spec   | End-to-end type safety, no manual interfaces.ts sync             |
| E2E testing           | Playwright + pytest-playwright | Fast, multi-browser, native Django integration                   |
| CSS                   | PrimeVue theme + minimal utils | Replace Bootstrap progressively                                  |
| Maps                  | OpenLayers (keep as-is)        | Wrap existing components, refactor to Composition API only       |
| Deployment            | Vite build step before collectstatic | Works for current VPS and future ECS                        |

## Migration Strategy: Page-by-Page on Main

The key principle: **every commit on main is shippable**. No feature flags, no parallel
URLs, no long-running branches.

Vite and Webpack coexist during the migration. Old pages load the Webpack bundle. New pages
load the Vite bundle. The shared navbar/footer (PrimeVue) is in the Vite bundle and mounted
on all pages (old and new) from the start.

## Phases

### Phase 0: Infrastructure Setup

Set up the new toolchain alongside the existing one. No user-visible changes.

- [x] 0.1 - Install Vite, configure `vite.config.ts` for Django integration
- [x] 0.2 - Install and configure `django-vite` (manifest mode for production,
        dev server proxy for development)
- [x] 0.3 - Install PrimeVue, Pinia, Vue Router
- [ ] 0.4 - Create new entry point (`assets/new-frontend/main.ts`) with Vue app,
        router, Pinia store, PrimeVue plugin, i18n
- [ ] 0.5 - Set up the project structure (see below)
- [ ] 0.6 - Verify: Vite dev server runs, production build works, django-vite
        injects assets into a test template, Webpack still works unchanged
- [ ] 0.7 - Install Django Ninja, create a minimal `/api/v2/` router (empty for now)
- [ ] 0.8 - Install Playwright, configure pytest-playwright, write one smoke test
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
    types/                # Auto-generated from OpenAPI (later)
  ts/                     # <-- existing Webpack-managed frontend (untouched)
    early_alert.ts
    components/
    ...
```

### Phase 1: Shared Layout (Navbar + Footer)

First user-visible change. All pages get the new look simultaneously.

- [ ] 1.1 - Build `NavBar.vue` and `FooterBar.vue` with PrimeVue components
        (Menubar, etc.), matching current navigation structure
- [ ] 1.2 - Update `base.html` to load the Vite bundle AND mount the new navbar/footer
        (alongside the existing Webpack bundle)
- [ ] 1.3 - Remove old Bootstrap navbar/footer HTML from `base.html`
- [ ] 1.4 - Verify all existing pages still work with the new layout
- [ ] 1.5 - Write Playwright tests for navbar navigation

**Note**: During this phase, page bodies still use Bootstrap. The visual contrast should be
mild since your custom CSS is minimal. If needed, add a small bridge stylesheet.

### Phase 2: Index Page + Observation Details

The most complex migration. Proves the full architecture. Solves the filter-loss problem.

- [ ] 2.1 - Create Django Ninja endpoints for data consumed by the index page:
        filtered observations (paginated), species list, datasets, areas,
        monthly histogram, observation counter
- [ ] 2.2 - Generate TypeScript types from OpenAPI spec (`openapi-typescript`)
- [ ] 2.3 - Create `filters` Pinia store (replaces the reactive filters object in
        IndexPageRootComponent)
- [ ] 2.4 - Migrate `IndexPage.vue`:
  - [ ] 2.4.1 - Page skeleton with PrimeVue layout
  - [ ] 2.4.2 - Filter components (species, datasets, areas, date range, status)
          using PrimeVue MultiSelect, Calendar, etc.
  - [ ] 2.4.3 - Observations DataTable (PrimeVue DataTable replaces custom table)
  - [ ] 2.4.4 - Observations map (wrap existing OpenLayers component, convert to
          Composition API)
  - [ ] 2.4.5 - Monthly histogram (keep D3 or consider PrimeVue Chart)
  - [ ] 2.4.6 - Filter state synced to URL query string (shareable URLs)
- [ ] 2.5 - Migrate `ObservationDetailPage.vue` as a Vue Router route:
  - [ ] 2.5.1 - Observation info display
  - [ ] 2.5.2 - Single observation map (wrap existing component)
  - [ ] 2.5.3 - Comments section
  - [ ] 2.5.4 - Back navigation preserves filters (Pinia + router)
- [ ] 2.6 - Update Django URL routing: index and observation detail served by a single
        Django view that renders the Vue SPA shell
- [ ] 2.7 - Remove old `index.html` and `observation_details.html` templates
- [ ] 2.8 - Remove `IndexPageRootComponent.vue` and related old components from
        `assets/ts/`
- [ ] 2.9 - Playwright tests for index page filters, data table, observation detail
        navigation (back button preserves filters)

### Phase 3: Alert CRUD

- [ ] 3.1 - Django Ninja endpoints for alert operations (create, read, update, delete,
        load-as-filters, suggest-name, available-intervals)
- [ ] 3.2 - Migrate `AlertDetailPage.vue` (with delete confirmation via PrimeVue
        ConfirmDialog)
- [ ] 3.3 - Migrate `AlertFormPage.vue` (create + edit, PrimeVue form components)
- [ ] 3.4 - Migrate `UserAlertsPage.vue` (alert list with delete buttons)
- [ ] 3.5 - Add Vue Router routes, update Django URL routing
- [ ] 3.6 - Remove old templates and components
- [ ] 3.7 - Playwright tests

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

- Vue Router history mode vs hash mode? History mode needs Django catch-all route config.
  Recommendation: history mode for cleaner URLs (Django catch-all is straightforward).
- PrimeVue theme customization: Aura preset out of the box, or customize colors to match
  project branding?
- Should the OpenAPI -> TypeScript generation be a build step or a manual/CI step?
