<script setup lang="ts">
import { ref, onMounted, watch, computed } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import { useRouter, useRoute } from "vue-router";
import Drawer from "primevue/drawer";
import ObservationDetailPanel from "../components/ObservationDetailPanel.vue";
import Card from "primevue/card";
import Tabs from "primevue/tabs";
import TabList from "primevue/tablist";
import Tab from "primevue/tab";
import TabPanels from "primevue/tabpanels";
import TabPanel from "primevue/tabpanel";
import DataTable, { type DataTablePageEvent, type DataTableSortEvent } from "primevue/datatable";
import Column from "primevue/column";
import FilterPanel from "../components/FilterPanel.vue";
import ObservationCounter from "../components/ObservationCounter.vue";
import ObservationHistogram from "../components/ObservationHistogram.vue";
import ObservationsMap from "../components/ObservationsMap.vue";
import { useFiltersStore } from "../stores/filters";
import { useFilterSync } from "../composables/useFilterSync";
import type { components } from "../types/api";

type ObservationOut = components["schemas"]["ObservationOut"];

const { t } = useI18n();

const filtersStore = useFiltersStore();
const router = useRouter();
const route = useRoute();

// Drawer is open when ?obs=<stableId> is in the URL.
// This means deep-links like /new/?obs=abc123 open the drawer on load.
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

useFilterSync();

const observations = ref<ObservationOut[]>([]);
const totalRecords = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const PAGE_SIZE = 20;
const sortField = ref("date");
const sortOrder = ref<1 | -1>(-1); // -1 = descending (PrimeVue convention)

function buildFilterParams(): URLSearchParams {
    const params = new URLSearchParams({
        page: String(currentPage.value),
        pageSize: String(PAGE_SIZE),
    });
    for (const id of filtersStore.speciesIds) params.append("speciesIds", String(id));
    for (const id of filtersStore.datasetsIds) params.append("datasetsIds", String(id));
    for (const id of filtersStore.areaIds) params.append("areaIds", String(id));
    for (const id of filtersStore.basisOfRecordIds) params.append("basisOfRecordIds", String(id));
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
    try {
        const response = await fetch(`/api/v2/observations/?${buildFilterParams()}`);
        const data = await response.json();
        observations.value = data.items;
        totalRecords.value = data.count;
    } finally {
        loading.value = false;
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

// Welcome text: page fragment rendered server-side, language-aware
const welcomeHtml = ref("");
async function loadWelcomeText() {
    const resp = await fetch("/api/v2/page-fragments/welcome_text/");
    if (resp.ok) {
        const data = await resp.json();
        welcomeHtml.value = data.html;
    }
}

onMounted(() => {
    loadObservations();
    loadWelcomeText();
});
</script>

<template>
    <div class="index-page">
        <!-- Welcome text (page fragment, rendered HTML from backend) -->
        <div v-if="welcomeHtml" class="welcome-text" v-html="welcomeHtml" />

        <!-- Filters -->
        <Card>
            <template #content>
                <FilterPanel />
            </template>
        </Card>

        <!-- Counter -->
        <ObservationCounter :count="totalRecords" :loading="loading" />

        <!-- Histogram -->
        <Card>
            <template #content>
                <ObservationHistogram />
            </template>
        </Card>

        <!-- Map / Table tabs -->
        <Tabs value="map">
            <TabList>
                <Tab value="map">{{ t("message.mapView") }}</Tab>
                <Tab value="table">{{ t("message.tableView") }}</Tab>
            </TabList>
            <TabPanels>
                <TabPanel value="map">
                    <ObservationsMap />
                </TabPanel>

                <TabPanel value="table">
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
                        class="observations-table"
                        @page="onPage"
                        @sort="onSort"
                        @row-click="(e) => openObservation(e.data.stableId)"
                    >
                        <Column field="date" :header="t('message.date')" sortable />
                        <Column field="scientificName" :header="t('message.species')" sortable>
                            <template #body="{ data }">
                                <a
                                    href="#"
                                    class="species-link"
                                    @click.prevent="openObservation(data.stableId)"
                                >
                                    <em>{{ data.scientificName }}</em>
                                    <span v-if="data.vernacularName">
                                        ({{ data.vernacularName }})
                                    </span>
                                </a>
                            </template>
                        </Column>
                        <Column field="datasetName" :header="t('message.dataset')" sortable />
                        <Column :header="t('message.gbifId')">
                            <template #body="{ data }">
                                <a
                                    :href="`https://www.gbif.org/occurrence/${data.gbifId}`"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="gbif-link"
                                    @click.stop
                                >{{ data.gbifId }}</a>
                            </template>
                        </Column>
                        <Column
                            v-if="observations.some((o) => o.seenByCurrentUser !== null)"
                            :header="t('message.seen')"
                        >
                            <template #body="{ data }">
                                <span v-if="data.seenByCurrentUser === true">&#10003;</span>
                                <span v-else-if="data.seenByCurrentUser === false">&bull;</span>
                            </template>
                        </Column>
                    </DataTable>
                </TabPanel>
            </TabPanels>
        </Tabs>

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
    </div>
</template>

<style scoped>
.index-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
}

.welcome-text {
    /* The fragment HTML comes from the Markdown renderer - give it standard prose spacing */
}

.welcome-text :deep(p) {
    margin: 0 0 0.75rem;
}

.welcome-text :deep(p:last-child) {
    margin-bottom: 0;
}

.species-link {
    color: inherit;
    text-decoration: none;
}

.species-link:hover {
    text-decoration: underline;
}

/* Make the entire row feel clickable */
.observations-table :deep(tbody tr) {
    cursor: pointer;
}

.gbif-link {
    color: var(--p-primary-color);
    font-size: 0.85rem;
}
</style>
