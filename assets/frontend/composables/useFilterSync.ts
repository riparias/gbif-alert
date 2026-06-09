import { watch } from "vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";
import { debounce } from "lodash";
import { useFiltersStore } from "../stores/filters";

// --- Query parsing helpers ---

function getIntArray(query: LocationQuery, key: string): number[] {
    const val = query[key];
    if (!val) return [];
    const arr = Array.isArray(val) ? val : [val];
    return arr.map(Number).filter((n) => !isNaN(n));
}

function getString(query: LocationQuery, key: string): string | null {
    const val = query[key];
    return typeof val === "string" ? val : null;
}

function getFloat(query: LocationQuery, key: string): number | null {
    const val = query[key];
    if (typeof val !== "string") return null;
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

// --- Query building ---

type QueryRecord = Record<string, string | string[]>;

function buildQuery(
    store: ReturnType<typeof useFiltersStore>,
    isAuthenticated: boolean,
): QueryRecord {
    const q: QueryRecord = {};
    if (store.speciesIds.length) q.speciesIds = store.speciesIds.map(String);
    if (store.datasetIds.length) q.datasetIds = store.datasetIds.map(String);
    if (store.basisOfRecordIds.length) q.basisOfRecordIds = store.basisOfRecordIds.map(String);
    if (store.areaIds.length) q.areaIds = store.areaIds.map(String);
    if (store.initialDataImportIds.length)
        q.initialDataImportIds = store.initialDataImportIds.map(String);
    if (store.startDate) q.startDate = store.startDate;
    if (store.endDate) q.endDate = store.endDate;
    if (isAuthenticated) {
        // For auth users "notViewed" is the default - omit it for a clean URL.
        // null means "all" - write explicitly so the user can bookmark/share it.
        if (store.status === null) q.status = "all";
        else if (store.status === "viewed") q.status = "viewed";
    } else {
        // For anonymous users null (all) is the default - omit it.
        // Explicit "viewed" or "notViewed" choices are written to the URL.
        if (store.status === "viewed") q.status = "viewed";
        else if (store.status === "notViewed") q.status = "notViewed";
    }
    if (store.verifiedFilter !== "all") q.verifiedFilter = store.verifiedFilter;
    if (store.areaFilterMode !== "inside") q.areaFilterMode = store.areaFilterMode;
    if (store.approachingDistanceKm !== null)
        q.approachingDistanceKm = String(store.approachingDistanceKm);
    return q;
}

// Compares a LocationQuery (from vue-router) with a plain query record.
// Arrays are order-insensitive since URL param order is not meaningful.
function queriesEqual(a: LocationQuery, b: QueryRecord): boolean {
    const aKeys = Object.keys(a).sort();
    const bKeys = Object.keys(b).sort();
    if (aKeys.join(",") !== bKeys.join(",")) return false;
    for (const k of aKeys) {
        const av = (Array.isArray(a[k]) ? a[k] : [a[k]]) as (string | null)[];
        const bv = (Array.isArray(b[k]) ? b[k] : [b[k]]) as string[];
        if ([...av].sort().join(",") !== [...bv].sort().join(",")) return false;
    }
    return true;
}

// --- Composable ---

export function useFilterSync(isAuthenticated: boolean = true): void {
    const route = useRoute();
    const router = useRouter();
    const store = useFiltersStore();

    // URL -> store: runs immediately on mount so the store is populated from the
    // URL before onMounted() fires (which triggers the first data load).
    watch(
        () => route.query,
        (query) => {
            const status = getString(query, "status");
            const verified = getString(query, "verifiedFilter");
            const areaMode = getString(query, "areaFilterMode");

            store.speciesIds = getIntArray(query, "speciesIds");
            store.datasetIds = getIntArray(query, "datasetIds");
            store.basisOfRecordIds = getIntArray(query, "basisOfRecordIds");
            store.areaIds = getIntArray(query, "areaIds");
            store.initialDataImportIds = getIntArray(query, "initialDataImportIds");
            store.startDate = getString(query, "startDate");
            store.endDate = getString(query, "endDate");
            // Auth users: "notViewed" is the default (no param); "all" in the URL means null.
            // Anonymous users: null (all) is the default (no param); "notViewed" must be explicit.
            if (isAuthenticated) {
                store.status =
                    status === "viewed"
                        ? "viewed"
                        : status === "all"
                          ? null
                          : "notViewed";
            } else {
                store.status =
                    status === "viewed"
                        ? "viewed"
                        : status === "notViewed"
                          ? "notViewed"
                          : null;
            }
            store.verifiedFilter =
                verified === "verified" || verified === "unverified" ? verified : "all";
            store.areaFilterMode =
                areaMode === "approaching" || areaMode === "both" ? areaMode : "inside";
            store.approachingDistanceKm = getFloat(query, "approachingDistanceKm");
        },
        { immediate: true }
    );

    // Store -> URL: debounced to avoid a router.replace on every keystroke.
    // Defaults (verifiedFilter=all, areaFilterMode=inside, empty arrays, null values)
    // are omitted so clean state produces a clean URL (?).
    // queriesEqual check prevents an infinite URL->store->URL cycle: when the URL
    // watch above updates the store with new array references but identical values,
    // the store watch fires but buildQuery() produces the same URL, so we skip
    // router.replace() and the cycle stops.
    const syncToUrl = debounce(() => {
        const q = buildQuery(store, isAuthenticated);
        // NOTE: The ?obs= param is managed by ObservationsView's drawer, not by the filter
        // store. We carry it through verbatim so that changing a filter does not
        // close an open drawer. It is intentionally excluded from buildQuery() to
        // keep the filter/drawer concerns separate.
        const obsParam = route.query.obs;
        if (typeof obsParam === "string") q.obs = obsParam;
        if (!queriesEqual(route.query, q)) {
            router.replace({ query: q });
        }
    }, 300);

    watch(store, syncToUrl, { deep: true });
}
