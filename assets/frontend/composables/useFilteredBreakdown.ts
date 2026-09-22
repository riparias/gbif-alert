import { computed, onMounted, onUnmounted, ref, watch, type Ref } from "vue";
import { debounce } from "lodash";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import { filtersToParams } from "../utils/filterParams";
import { useLatestRequest } from "./useLatestRequest";

/**
 * Rows of a per-filter breakdown endpoint (species, datasets), reloaded on
 * every filter change and on every seen/unseen status change.
 *
 * On demand: while the tab is hidden a filter change only marks the data
 * stale, and the fetch happens when the tab becomes active again. The panel
 * stays mounted once visited, so visibility has to come from the parent.
 */
export function useFilteredBreakdown<T extends { count: number }>(
    endpoint: string,
    active: Ref<boolean>,
) {
    const filtersStore = useFiltersStore();
    const resultsStore = useResultsStore();
    const rows = ref<T[]>([]) as Ref<T[]>;
    const { loading, error, load: fetchLatest } = useLatestRequest<T[]>();
    const stale = ref(true);

    const total = computed(() => rows.value.reduce((sum, row) => sum + row.count, 0));

    /** A row's count as a percentage of all rows' counts. */
    function share(count: number): number {
        return total.value === 0 ? 0 : (count / total.value) * 100;
    }

    async function load() {
        const data = await fetchLatest(`${endpoint}?${filtersToParams(filtersStore)}`);
        if (data === undefined) return; // superseded, or failed (error is set)
        rows.value = data;
        stale.value = false;
    }

    function loadIfActive() {
        if (active.value) {
            load();
        } else {
            stale.value = true;
        }
    }

    const debouncedReload = debounce(loadIfActive, 300);

    watch(filtersStore, debouncedReload, { deep: true });
    watch(() => resultsStore.statusEpoch, debouncedReload);
    watch(active, (isActive) => {
        if (isActive && stale.value) load();
    });

    onMounted(() => {
        if (active.value) load();
    });
    onUnmounted(() => debouncedReload.cancel());

    return { rows, loading, error, load, share };
}
