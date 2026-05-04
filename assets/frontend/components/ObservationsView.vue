<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import { useRouter, useRoute } from "vue-router";
import Drawer from "primevue/drawer";
import ObservationDetailPanel from "./ObservationDetailPanel.vue";
import DataTable, { type DataTablePageEvent, type DataTableSortEvent } from "primevue/datatable";
import Column from "primevue/column";
import Button from "primevue/button";
import Popover from "primevue/popover";
import Checkbox from "primevue/checkbox";
import ObservationHistogram from "./ObservationHistogram.vue";
import ObservationsMap from "./ObservationsMap.vue";
import Tabs from "primevue/tabs";
import TabList from "primevue/tablist";
import Tab from "primevue/tab";
import TabPanels from "primevue/tabpanels";
import TabPanel from "primevue/tabpanel";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import type { components } from "../types/api";
import SpeciesName from "./SpeciesName.vue";
import { storeToRefs } from "pinia";
import { usePreferencesStore } from "../stores/preferences";

type ObservationOut = components["schemas"]["ObservationOut"];

const props = defineProps<{
    unseenFallback?: boolean;
}>();

const resultsStore = useResultsStore();

const { t } = useI18n();
const filtersStore = useFiltersStore();
const router = useRouter();
const route = useRoute();

// --- Drawer ---

const drawerStableId = computed(() => {
    const obs = route.query.obs;
    return typeof obs === "string" ? obs : null;
});

function openObservation(stableId: string) {
    router.replace({ query: { ...route.query, obs: stableId } });
}

function closeDrawer() {
    const q = { ...route.query };
    delete q.obs;
    router.replace({ query: q });
}

// --- Column configuration ---

const COLUMN_DEFS = [
    { key: "date",          sortField: "date",           defaultVisible: true  },
    { key: "species",       sortField: null, defaultVisible: true  },
    { key: "dataset",       sortField: "datasetName",    defaultVisible: true  },
    { key: "municipality",  sortField: "municipality",   defaultVisible: true  },
    { key: "verified",      sortField: "verified",       defaultVisible: true  },
    { key: "basisOfRecord", sortField: null,             defaultVisible: true  },
    { key: "gbifId",        sortField: null,             defaultVisible: false },
    { key: "seen",          sortField: null,             defaultVisible: true  },
] as const;

type ColumnKey = (typeof COLUMN_DEFS)[number]["key"];

const LS_KEY = "gbif-alert.tableColumns";

function loadVisibleColumns(): Set<ColumnKey> {
    try {
        const stored = localStorage.getItem(LS_KEY);
        if (stored) {
            const parsed: unknown = JSON.parse(stored);
            if (Array.isArray(parsed)) {
                const validKeys = new Set(COLUMN_DEFS.map((c) => c.key));
                return new Set(
                    (parsed as string[]).filter((k) => validKeys.has(k as ColumnKey)) as ColumnKey[]
                );
            }
        }
    } catch {
        // ignore parse errors
    }
    return new Set(COLUMN_DEFS.filter((c) => c.defaultVisible).map((c) => c.key));
}

const visibleColumns = ref<Set<ColumnKey>>(loadVisibleColumns());

function toggleColumn(key: ColumnKey) {
    const next = new Set(visibleColumns.value);
    if (next.has(key)) { next.delete(key); } else { next.add(key); }
    visibleColumns.value = next;
    localStorage.setItem(LS_KEY, JSON.stringify([...next]));
}

const columnPopover = ref();

// --- Observation fetching ---

const observations = ref<ObservationOut[]>([]);
const hasSeen = computed(() => observations.value.some((o) => o.seenByCurrentUser !== null));
const totalRecords = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const PAGE_SIZE = 20;
const sortField = ref("date");
const sortOrder = ref<1 | -1>(-1);

const preferences = usePreferencesStore();
const { speciesNameMode } = storeToRefs(preferences);

// The species column's wire-level sort field follows the user's display preference.
const speciesSortFieldName = computed<string>(() =>
    speciesNameMode.value === "vernacular" ? "vernacularName" : "scientificName",
);

function buildFilterParams(): URLSearchParams {
    const params = new URLSearchParams({
        page: String(currentPage.value),
        pageSize: String(PAGE_SIZE),
    });
    for (const id of filtersStore.speciesIds) params.append("speciesIds", String(id));
    for (const id of filtersStore.datasetsIds) params.append("datasetsIds", String(id));
    for (const id of filtersStore.areaIds) params.append("areaIds", String(id));
    for (const id of filtersStore.basisOfRecordIds) params.append("basisOfRecordIds", String(id));
    for (const id of filtersStore.initialDataImportIds) params.append("initialDataImportIds", String(id));
    if (filtersStore.startDate) params.set("startDate", filtersStore.startDate);
    if (filtersStore.endDate) params.set("endDate", filtersStore.endDate);
    if (filtersStore.status) params.set("status", filtersStore.status);
    params.set("verifiedFilter", filtersStore.verifiedFilter);
    params.set("areaFilterMode", filtersStore.areaFilterMode);
    if (filtersStore.approachingDistanceKm !== null)
        params.set("approachingDistanceKm", String(filtersStore.approachingDistanceKm));
    params.set("orderBy", sortField.value);
    params.set("orderDir", sortOrder.value === 1 ? "asc" : "desc");
    return params;
}

async function loadObservations() {
    loading.value = true;
    resultsStore.loading = true;
    try {
        const response = await fetch(`/api/v2/observations/?${buildFilterParams()}`);
        if (response.ok) {
            const data = await response.json();
            observations.value = data.items;
            totalRecords.value = data.count;
            resultsStore.observationCount = data.count;
            resultsStore.speciesCount = data.speciesCount;
            resultsStore.datasetsCount = data.datasetsCount;
        }
    } finally {
        loading.value = false;
        resultsStore.loading = false;
    }
}

function onPage(event: DataTablePageEvent) {
    currentPage.value = event.page + 1;
    loadObservations();
}

function onSort(event: DataTableSortEvent) {
    sortField.value = String(event.sortField ?? "date");
    sortOrder.value = (event.sortOrder ?? -1) as 1 | -1;
    currentPage.value = 1;
    loadObservations();
}

const reloadOnFilterChange = debounce(() => {
    currentPage.value = 1;
    loadObservations();
}, 300);

watch(filtersStore, reloadOnFilterChange, { deep: true });

// When the user flips the navbar species-name toggle while sorted on the
// species column, re-issue the request so the backend sorts by the field
// that matches what they now see. Direction is preserved.
watch(speciesNameMode, () => {
    if (sortField.value === "scientificName" || sortField.value === "vernacularName") {
        sortField.value = speciesSortFieldName.value;
        currentPage.value = 1;
        loadObservations();
    }
});

onUnmounted(() => reloadOnFilterChange.cancel());

onMounted(async () => {
    await loadObservations();
    // props.unseenFallback is evaluated once at mount; the fallback is first-load-only
    // behaviour, not something that re-runs when filters change.
    if (props.unseenFallback && totalRecords.value === 0 && filtersStore.status === "unseen") {
        filtersStore.status = null;
        reloadOnFilterChange.cancel();
        await loadObservations();
    }
});
</script>

<template>
    <!-- Empty state -->
    <div v-if="!loading && totalRecords === 0" class="empty-state">
        <span class="empty-state-icon">&#128269;</span>
        <p class="empty-state-title">{{ t("message.noMatchingResultsFound") }}</p>
        <p class="empty-state-hint">{{ t("message.noMatchingResultsFoundHint") }}</p>
    </div>

    <template v-else>
        <!-- Map / Timeline / Table tabs -->
        <Tabs value="map">
            <TabList>
                <Tab value="map"><i class="pi pi-map" /> {{ t("message.mapView") }}</Tab>
                <Tab value="timeline"><i class="pi pi-chart-bar" /> {{ t("message.timelineView") }} <span class="tab-new-badge">{{ t("message.newBadge") }}</span></Tab>
                <Tab value="table"><i class="pi pi-table" /> {{ t("message.tableView") }}</Tab>
            </TabList>
            <TabPanels>
                <TabPanel value="map">
                    <ObservationsMap />
                </TabPanel>

                <TabPanel value="timeline">
                    <ObservationHistogram />
                </TabPanel>

                <TabPanel value="table">
                    <!-- Column picker toolbar -->
                    <div class="table-toolbar">
                        <Button
                            icon="pi pi-sliders-h"
                            text
                            size="small"
                            @click="(e) => columnPopover.toggle(e)"
                            aria-label="Configure visible columns"
                        />
                        <Popover ref="columnPopover">
                            <div class="column-picker">
                                <div
                                    v-for="col in COLUMN_DEFS.filter((c) => c.key !== 'seen' || hasSeen)"
                                    :key="col.key"
                                    class="column-picker-item"
                                >
                                    <Checkbox
                                        :input-id="`col-${col.key}`"
                                        :model-value="visibleColumns.has(col.key)"
                                        :binary="true"
                                        @update:model-value="toggleColumn(col.key)"
                                    />
                                    <label :for="`col-${col.key}`">{{ t(`message.${col.key}`) }}</label>
                                </div>
                            </div>
                        </Popover>
                    </div>

                    <DataTable
                        :value="observations"
                        lazy
                        paginator
                        :rows="PAGE_SIZE"
                        :total-records="totalRecords"
                        :loading="loading"
                        :sort-field="sortField"
                        :sort-order="sortOrder"
                        row-hover
                        resizable-columns
                        column-resize-mode="fit"
                        class="observations-table"
                        @page="onPage"
                        @sort="onSort"
                        @row-click="(e) => openObservation(e.data.stableId)"
                    >
                        <Column v-if="visibleColumns.has('date')" field="date" :header="t('message.date')" sortable />
                        <Column
                            v-if="visibleColumns.has('species')"
                            :field="speciesSortFieldName"
                            :header="t('message.species')"
                            sortable
                        >
                            <template #body="{ data }">
                                <SpeciesName
                                    :scientific-name="data.scientificName"
                                    :vernacular-name="data.vernacularName"
                                />
                            </template>
                        </Column>
                        <Column v-if="visibleColumns.has('dataset')" field="datasetName" :header="t('message.dataset')" sortable header-class="col-dataset" body-class="col-dataset">
                            <template #body="{ data }">
                                <span class="cell-text" :title="data.datasetName">{{ data.datasetName }}</span>
                            </template>
                        </Column>
                        <Column v-if="visibleColumns.has('municipality')" field="municipality" :header="t('message.municipality')" sortable>
                            <template #body="{ data }">
                                <span class="cell-text" :title="data.municipality || undefined">{{ data.municipality || '-' }}</span>
                            </template>
                        </Column>
                        <Column v-if="visibleColumns.has('verified')" field="verified" :header="t('message.verified')" sortable>
                            <template #body="{ data }">
                                <span class="verified-badge" :class="data.verified ? 'badge-success' : 'badge-danger'" :title="data.identificationVerificationStatus || undefined">
                                    {{ data.verified ? t('message.verified') : t('message.unverified') }}
                                </span>
                            </template>
                        </Column>
                        <Column v-if="visibleColumns.has('basisOfRecord')" :header="t('message.basisOfRecord')">
                            <template #body="{ data }">
                                <span class="cell-text" :title="data.basisOfRecord">{{ data.basisOfRecord }}</span>
                            </template>
                        </Column>
                        <Column v-if="visibleColumns.has('gbifId')" :header="t('message.gbifId')">
                            <template #body="{ data }">
                                <a :href="`https://www.gbif.org/occurrence/${data.gbifId}`" target="_blank" rel="noopener noreferrer" class="gbif-link" @click.stop>{{ data.gbifId }}</a>
                            </template>
                        </Column>
                        <Column v-if="visibleColumns.has('seen') && hasSeen" :header="t('message.seen')">
                            <template #body="{ data }">
                                <span v-if="data.seenByCurrentUser === true">&#10003;</span>
                                <span v-else-if="data.seenByCurrentUser === false">&bull;</span>
                            </template>
                        </Column>
                    </DataTable>
                </TabPanel>
            </TabPanels>
        </Tabs>
    </template>

    <Drawer
        :visible="drawerStableId !== null"
        position="right"
        :style="{ width: 'min(45rem, 95vw)' }"
        @update:visible="(v) => !v && closeDrawer()"
    >
        <ObservationDetailPanel
            v-if="drawerStableId"
            :stable-id="drawerStableId"
            @close="closeDrawer"
        />
    </Drawer>
</template>

<style scoped>
.observations-table :deep(tbody tr) { cursor: pointer; }
.observations-table :deep(table) { table-layout: fixed; }
.observations-table :deep(th.col-dataset),
.observations-table :deep(td.col-dataset) { width: 180px; }
.gbif-link { color: var(--p-primary-color); font-size: 0.85rem; }
.empty-state { display: flex; flex-direction: column; align-items: center; padding: 3rem 1rem; gap: 0.5rem; color: var(--p-text-muted-color); }
.empty-state-icon { font-size: 2.5rem; line-height: 1; }
.empty-state-title { margin: 0; font-size: 1.1rem; font-weight: 600; color: var(--p-text-color); }
.empty-state-hint { margin: 0; font-size: 0.9rem; }
.table-toolbar { display: flex; justify-content: flex-end; padding: 0.25rem 0; }
.column-picker { display: flex; flex-direction: column; gap: 0.5rem; min-width: 160px; }
.column-picker-item { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
.column-picker-item label { cursor: pointer; user-select: none; }
.cell-text { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.observations-table :deep(td) { overflow: hidden; }
.tab-new-badge {
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    background: var(--p-primary-500, #00a58d);
    color: #fff;
    border-radius: 999px;
    padding: 0.1rem 0.35rem;
    vertical-align: middle;
    margin-left: 0.25rem;
    animation: badge-pulse 2s ease-in-out infinite;
}

@keyframes badge-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
</style>
