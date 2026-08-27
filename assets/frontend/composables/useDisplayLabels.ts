import { useFilterOptionsStore } from "../stores/filterOptions";

// Resolves option ids (and the email-frequency enum) to their human-readable
// names. The backend now returns ids instead of pre-formatted labels (audit
// N5/N7), so the SPA does the join.
//
// Lists are loaded lazily: ObservationsView renders on the alert detail page
// and the alert pages render cards/sidebars, none of which have a FilterSidebar
// to populate filterOptionsStore. Each loader is load-if-empty (idempotent).
//
// The in-flight map below makes them safe to call repeatedly in quick
// succession, which the mobile layout now does: the filter sidebar lives inside
// a drawer that unmounts its content on close, so every reopen re-runs the
// loaders. Without it, two opens in a row would fire two identical requests.
const inFlight = new Map<string, Promise<void>>();

function loadOnce(key: string, load: () => Promise<void>): Promise<void> {
    const pending = inFlight.get(key);
    if (pending) return pending;
    const promise = load().finally(() => inFlight.delete(key));
    inFlight.set(key, promise);
    return promise;
}

export function useDisplayLabels() {
    const store = useFilterOptionsStore();

    async function ensureSpeciesLoaded(): Promise<void> {
        if (store.species.length) return;
        return loadOnce("species", async () => {
            const res = await fetch("/api/v2/species/");
            if (res.ok) store.species = await res.json();
        });
    }

    async function ensureBasisOfRecordLoaded(): Promise<void> {
        if (store.basisOfRecord.length) return;
        return loadOnce("basisOfRecord", async () => {
            const res = await fetch("/api/v2/basis-of-record/");
            if (res.ok) store.basisOfRecord = await res.json();
        });
    }

    async function ensureDatasetsLoaded(): Promise<void> {
        if (store.datasets.length) return;
        return loadOnce("datasets", async () => {
            const res = await fetch("/api/v2/datasets/");
            if (res.ok) store.datasets = await res.json();
        });
    }

    async function ensureAreasLoaded(): Promise<void> {
        if (store.areas.length) return;
        return loadOnce("areas", async () => {
            const res = await fetch("/api/v2/areas/");
            if (res.ok) store.areas = await res.json();
        });
    }

    async function ensureFrequenciesLoaded(): Promise<void> {
        if (store.frequencies.length) return;
        return loadOnce("frequencies", async () => {
            const res = await fetch("/api/v2/alerts/notification-frequencies/");
            if (res.ok) store.frequencies = await res.json();
        });
    }

    // The lookup lists the alert pages need to render an alert's filters.
    async function ensureAlertLabelsLoaded(): Promise<void> {
        await Promise.all([
            ensureDatasetsLoaded(),
            ensureAreasLoaded(),
            ensureBasisOfRecordLoaded(),
            ensureFrequenciesLoaded(),
        ]);
    }

    // Everything FilterSidebar needs to render its controls.
    async function ensureFilterOptionsLoaded(): Promise<void> {
        await Promise.all([
            ensureSpeciesLoaded(),
            ensureDatasetsLoaded(),
            ensureAreasLoaded(),
            ensureBasisOfRecordLoaded(),
        ]);
    }

    function basisOfRecordName(id: number): string {
        return store.basisOfRecord.find((b) => b.id === id)?.name ?? "";
    }

    function datasetName(id: number): string {
        return store.datasets.find((d) => d.id === id)?.name ?? "";
    }

    function areaName(id: number): string {
        return store.areas.find((a) => a.id === id)?.name ?? "";
    }

    // Frequencies are keyed by their enum code (e.g. "W"); fall back to the code.
    function frequencyLabel(id: string): string {
        return store.frequencies.find((f) => f.id === id)?.label ?? id;
    }

    return {
        ensureBasisOfRecordLoaded,
        ensureAlertLabelsLoaded,
        ensureFilterOptionsLoaded,
        basisOfRecordName,
        datasetName,
        areaName,
        frequencyLabel,
    };
}
