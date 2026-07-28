<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import { filtersToParams } from "../utils/filterParams";
import { pickVernacular } from "../utils/vernacular";
import SpeciesName from "./SpeciesName.vue";
import type { components } from "../types/api";

type SpeciesCountOut = components["schemas"]["SpeciesCountOut"];

const props = defineProps<{ active: boolean }>();

const { t, locale } = useI18n();
const filtersStore = useFiltersStore();
const resultsStore = useResultsStore();

const rows = ref<SpeciesCountOut[]>([]);
const loading = ref(false);
const stale = ref(true);

const total = computed(() => rows.value.reduce((sum, row) => sum + row.count, 0));

function share(count: number): number {
    return total.value === 0 ? 0 : (count / total.value) * 100;
}

async function load() {
    loading.value = true;
    try {
        const response = await fetch(
            `/api/v2/observations/species-breakdown/?${filtersToParams(filtersStore)}`,
        );
        if (response.ok) {
            rows.value = await response.json();
            stale.value = false;
        }
    } finally {
        loading.value = false;
    }
}

// On demand: while the tab is hidden a filter change only marks the data
// stale, and the fetch happens when the tab becomes active again. The panel
// stays mounted once visited, so visibility has to come from the parent.
function loadIfActive() {
    if (props.active) {
        load();
    } else {
        stale.value = true;
    }
}

const debouncedReload = debounce(loadIfActive, 300);

watch(filtersStore, debouncedReload, { deep: true });
watch(() => resultsStore.statusEpoch, debouncedReload);
watch(
    () => props.active,
    (isActive) => {
        if (isActive && stale.value) load();
    },
);

onMounted(() => {
    if (props.active) load();
});
onUnmounted(() => debouncedReload.cancel());
</script>

<template>
    <DataTable
        :value="rows"
        :loading="loading"
        sort-field="count"
        :sort-order="-1"
        row-hover
        class="species-breakdown-table"
    >
        <Column field="scientificName" :header="t('message.species')" sortable>
            <template #body="{ data }">
                <SpeciesName
                    :scientific-name="data.scientificName"
                    :vernacular-name="pickVernacular(data, locale)"
                />
            </template>
        </Column>
        <Column field="count" :header="t('message.observationCount')" sortable />
        <Column :header="t('message.shareOfResults')">
            <template #body="{ data }">
                <div class="share-cell">
                    <div class="share-track">
                        <div class="share-bar" :style="{ width: `${share(data.count)}%` }" />
                    </div>
                    <span class="share-value">{{ share(data.count).toFixed(1) }}%</span>
                </div>
            </template>
        </Column>
    </DataTable>
</template>

<style scoped>
.share-cell {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.share-track {
    flex: 1;
    min-width: 3rem;
    height: 0.5rem;
    background: var(--p-content-border-color);
    border-radius: 999px;
    overflow: hidden;
}
.share-bar {
    height: 100%;
    background: var(--p-primary-color);
}
.share-value {
    font-variant-numeric: tabular-nums;
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
    min-width: 3.5rem;
    text-align: right;
}
</style>
