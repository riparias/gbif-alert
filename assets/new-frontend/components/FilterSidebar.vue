<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import MultiSelect from "primevue/multiselect";
import Select from "primevue/select";
import SelectButton from "primevue/selectbutton";
import DatePicker from "primevue/datepicker";
import InputNumber from "primevue/inputnumber";
import SpeciesFilterModal from "./SpeciesFilterModal.vue";
import AreaFilterModal from "./AreaFilterModal.vue";
import DatasetFilterModal from "./DatasetFilterModal.vue";
import ObservationStatusToggle from "./ObservationStatusToggle.vue";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import { useFilterOptionsStore } from "../stores/filterOptions";
import type { components } from "../types/api";
import { getNavConfig } from "../utils/navConfig";

type SpeciesOut = components["schemas"]["SpeciesOut"];
type DatasetOut = components["schemas"]["DatasetOut"];
type AreaOut = components["schemas"]["AreaOut"];
type BasisOfRecordOut = components["schemas"]["BasisOfRecordOut"];

const { t } = useI18n();
const filtersStore = useFiltersStore();
const resultsStore = useResultsStore();
const filterOptionsStore = useFilterOptionsStore();

// Auth state from the nav config Django injects on every page
const isAuthenticated: boolean = getNavConfig().user.isAuthenticated;

// --- Available filter options (loaded from API on mount) ---

const speciesOptions = ref<SpeciesOut[]>([]);
const datasetOptions = ref<DatasetOut[]>([]);
const areaOptions = ref<AreaOut[]>([]);
const basisOfRecordOptions = ref<BasisOfRecordOut[]>([]);

onMounted(async () => {
    const [species, datasets, areas, basisOfRecord] = await Promise.all([
        fetch("/api/v2/species/").then((r) => r.json()),
        fetch("/api/v2/datasets/").then((r) => r.json()),
        fetch("/api/v2/areas/").then((r) => r.json()),
        fetch("/api/v2/basis-of-record/").then((r) => r.json()),
    ]);
    speciesOptions.value = species;
    datasetOptions.value = datasets;
    areaOptions.value = areas;
    basisOfRecordOptions.value = basisOfRecord;

    // Share loaded options so sibling components (e.g. ActiveFilterChips) can
    // resolve IDs to names without making duplicate API requests.
    filterOptionsStore.species = species;
    filterOptionsStore.datasets = datasets;
    filterOptionsStore.areas = areas;
    filterOptionsStore.basisOfRecord = basisOfRecord;
});

// --- v-model bindings to the Pinia store (computed get/set) ---

const selectedSpeciesIds = computed({
    get: () => filtersStore.speciesIds,
    set: (val: number[]) => {
        filtersStore.speciesIds = val;
    },
});

const selectedDatasetIds = computed({
    get: () => filtersStore.datasetsIds,
    set: (val: number[]) => {
        filtersStore.datasetsIds = val;
    },
});

const selectedAreaIds = computed({
    get: () => filtersStore.areaIds,
    set: (val: number[]) => {
        filtersStore.areaIds = val;
    },
});

const selectedBasisOfRecordIds = computed({
    get: () => filtersStore.basisOfRecordIds,
    set: (val: number[]) => {
        filtersStore.basisOfRecordIds = val;
    },
});

// Dates: store holds "YYYY-MM-DD" strings; DatePicker works with Date objects
function dateToString(d: Date | null): string | null {
    if (!d) return null;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

function stringToDate(s: string | null): Date | null {
    if (!s) return null;
    const [y, mo, d] = s.split("-").map(Number);
    return new Date(y, mo - 1, d);
}

const startDateObj = computed({
    get: () => stringToDate(filtersStore.startDate),
    set: (d: Date | null) => {
        filtersStore.startDate = dateToString(d);
    },
});

const endDateObj = computed({
    get: () => stringToDate(filtersStore.endDate),
    set: (d: Date | null) => {
        filtersStore.endDate = dateToString(d);
    },
});

const selectedVerifiedFilter = computed({
    get: () => filtersStore.verifiedFilter,
    set: (val: "all" | "verified" | "unverified") => {
        filtersStore.verifiedFilter = val;
    },
});

const selectedAreaFilterMode = computed({
    get: () => filtersStore.areaFilterMode,
    set: (val: "inside" | "approaching" | "both") => {
        filtersStore.areaFilterMode = val;
    },
});

const approachingDistanceKm = computed({
    get: () => filtersStore.approachingDistanceKm,
    set: (val: number | null) => {
        filtersStore.approachingDistanceKm = val;
    },
});

// --- Derived state ---

const hasAreaSelection = computed(() => filtersStore.areaIds.length > 0);
const showApproachingDistance = computed(
    () =>
        hasAreaSelection.value &&
        (filtersStore.areaFilterMode === "approaching" ||
            filtersStore.areaFilterMode === "both")
);

// Reset area-related filters when the area selection is cleared
watch(
    () => filtersStore.areaIds,
    (ids) => {
        if (ids.length === 0) {
            filtersStore.areaFilterMode = "inside";
            filtersStore.approachingDistanceKm = null;
        }
    }
);

// Default approaching distance to 5 km when the mode first requires it
watch(
    () => filtersStore.areaFilterMode,
    (mode) => {
        if (
            (mode === "approaching" || mode === "both") &&
            filtersStore.approachingDistanceKm === null
        ) {
            filtersStore.approachingDistanceKm = 5;
        }
    }
);

// --- Select options (static) ---

const verifiedFilterOptions = computed(() => [
    { value: "all", label: t("message.all") },
    { value: "verified", label: t("message.verifiedOnly") },
    { value: "unverified", label: t("message.unverifiedOnly") },
]);

const areaFilterModeOptions = computed(() => [
    { value: "inside", label: t("message.areaFilterModeInside") },
    { value: "approaching", label: t("message.areaFilterModeApproaching") },
    { value: "both", label: t("message.areaFilterModeBoth") },
]);

// --- Results stat ---

// Show "--" only on the initial load (count still 0). Once a count has been
// fetched, keep showing the last known value during filter/sort reloads so the
// counter doesn't flash "--" on every interaction.
const formattedCount = computed(() =>
    resultsStore.loading && resultsStore.observationCount === 0
        ? "--"
        : resultsStore.observationCount.toLocaleString()
);

const formattedSpeciesCount = computed(() =>
    resultsStore.loading && resultsStore.speciesCount === 0
        ? "--"
        : resultsStore.speciesCount.toLocaleString()
);

const formattedDatasetsCount = computed(() =>
    resultsStore.loading && resultsStore.datasetsCount === 0
        ? "--"
        : resultsStore.datasetsCount.toLocaleString()
);
</script>

<template>
    <div class="filter-sidebar-panel">
        <div class="sidebar-heading">{{ t("message.filters").toUpperCase() }}</div>

        <!-- WHAT section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading">{{ t("message.filterSectionWhat") }}</div>

            <div class="filter-group">
                <label>{{ t("message.species") }}</label>
                <SpeciesFilterModal
                    v-model="selectedSpeciesIds"
                    :options="speciesOptions"
                />
            </div>

            <div class="filter-group">
                <label>{{ t("message.dataset") }}</label>
                <DatasetFilterModal
                    v-model="selectedDatasetIds"
                    :options="datasetOptions"
                />
            </div>

            <div class="filter-group">
                <label>{{ t("message.basisOfRecord") }}</label>
                <MultiSelect
                    v-model="selectedBasisOfRecordIds"
                    :options="basisOfRecordOptions"
                    option-value="id"
                    option-label="name"
                    filter
                    :placeholder="t('message.allBasisOfRecord')"
                    :selected-items-label="`{0} ${t('message.xSelectedBasisOfRecord')}`"
                    :max-selected-labels="0"
                    class="sidebar-control"
                />
            </div>
        </div>

        <!-- WHERE section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading">{{ t("message.filterSectionWhere") }}</div>

            <div class="filter-group">
                <label>{{ t("message.area") }}</label>
                <AreaFilterModal
                    v-model="selectedAreaIds"
                    :options="areaOptions"
                />
            </div>

            <!-- Area filter mode (only when areas are selected) -->
            <div v-if="hasAreaSelection" class="filter-group">
                <label>{{ t("message.areaFilterMode") }}</label>
                <Select
                    v-model="selectedAreaFilterMode"
                    :options="areaFilterModeOptions"
                    option-value="value"
                    option-label="label"
                    class="sidebar-control"
                />
            </div>

            <!-- Approaching distance (only when mode requires it) -->
            <div v-if="showApproachingDistance" class="filter-group">
                <label>{{ t("message.approachingDistanceKm") }}</label>
                <InputNumber
                    v-model="approachingDistanceKm"
                    :min="0.1"
                    :max="50"
                    :step="0.1"
                    :min-fraction-digits="1"
                    :max-fraction-digits="1"
                    class="sidebar-control"
                />
            </div>
        </div>

        <!-- WHEN section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading">{{ t("message.filterSectionWhen") }}</div>

            <div class="filter-group">
                <label>{{ t("message.dateFrom") }}</label>
                <DatePicker
                    v-model="startDateObj"
                    date-format="yy-mm-dd"
                    show-button-bar
                    class="sidebar-control"
                />
            </div>

            <div class="filter-group">
                <label>{{ t("message.dateTo") }}</label>
                <DatePicker
                    v-model="endDateObj"
                    date-format="yy-mm-dd"
                    show-button-bar
                    class="sidebar-control"
                />
            </div>
        </div>

        <!-- STATUS section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading">{{ t("message.filterSectionStatus") }}</div>

            <div class="filter-group">
                <label>{{ t("message.verificationFilter") }}</label>
                <SelectButton
                    v-model="selectedVerifiedFilter"
                    :options="verifiedFilterOptions"
                    option-value="value"
                    option-label="label"
                    :allow-empty="false"
                    class="verified-select-button"
                />
            </div>

            <!-- Observation status (authenticated users only) -->
            <div v-if="isAuthenticated" class="filter-group">
                <label>{{ t("message.observationStatus") }}</label>
                <ObservationStatusToggle />
            </div>
        </div>

        <!-- Stat block -->
        <div class="stat-block">
            <div class="stat-main">
                <span class="stat-count">{{ formattedCount }}</span>
                <span class="stat-label">{{ t("message.statObservationsLabel") }}</span>
            </div>
            <div class="stat-cards">
                <div class="stat-card">
                    <span class="stat-card-value">{{ formattedSpeciesCount }}</span>
                    <span class="stat-card-label">{{ t("message.statSpeciesLabel") }}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value">{{ formattedDatasetsCount }}</span>
                    <span class="stat-card-label">{{ t("message.statDatasetsLabel") }}</span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.filter-sidebar-panel {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 0.75rem;
    height: 100%;
}

.sidebar-heading {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #64748b; /* slate-500 - muted on dark */
    text-transform: uppercase;
}

.sidebar-section {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #334155; /* slate-700 */
}

.sidebar-section:last-of-type {
    border-bottom: none;
    padding-bottom: 0;
}

.sidebar-section-heading {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: #475569; /* slate-600 - subtler than the main FILTERS heading */
    text-transform: uppercase;
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
}

.filter-group label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #94a3b8; /* slate-400 - readable on dark */
}

.sidebar-control {
    width: 100%;
}

:deep(.filter-modal-trigger) {
    width: 100%;
    justify-content: flex-start;
}

/* Compact sizing for all SelectButton toggles inside the sidebar */
.filter-group :deep(.p-selectbutton .p-togglebutton) {
    flex: 1;
    font-size: 0.78rem;
    padding: 0.25rem 0.35rem;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Verified filter: All (1st) slate, Verified (2nd) green, Unverified (3rd) red */
:deep(.verified-select-button .p-togglebutton:nth-child(1).p-togglebutton-checked),
:deep(.verified-select-button .p-togglebutton:nth-child(1).p-togglebutton-checked *) {
    background: #475569;
    border-color: #475569;
    color: #fff;
}

:deep(.verified-select-button .p-togglebutton:nth-child(2).p-togglebutton-checked),
:deep(.verified-select-button .p-togglebutton:nth-child(2).p-togglebutton-checked *) {
    background: #16a34a;
    border-color: #16a34a;
    color: #fff;
}

:deep(.verified-select-button .p-togglebutton:nth-child(3).p-togglebutton-checked),
:deep(.verified-select-button .p-togglebutton:nth-child(3).p-togglebutton-checked *) {
    background: #dc2626;
    border-color: #dc2626;
    color: #fff;
}

.stat-block {
    margin-top: auto;
    border-top: 1px solid #334155; /* slate-700 */
    padding-top: 1rem;
}

.stat-main {
    display: flex;
    flex-direction: column;
    line-height: 1.1;
    margin-bottom: 0.75rem;
}

.stat-count {
    font-size: 2rem;
    font-weight: 700;
    color: #f1f5f9; /* slate-100 */
}

.stat-label {
    font-size: 0.8rem;
    color: #64748b; /* slate-500 */
}

.stat-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
}

.stat-card {
    display: flex;
    flex-direction: column;
    background: #0f172a; /* slate-900 - darker inset card */
    border: 1px solid #334155; /* slate-700 */
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    line-height: 1.2;
}

.stat-card-value {
    font-size: 1.1rem;
    font-weight: 700;
    color: #f1f5f9; /* slate-100 */
}

.stat-card-label {
    font-size: 0.72rem;
    color: #64748b; /* slate-500 */
}
</style>
