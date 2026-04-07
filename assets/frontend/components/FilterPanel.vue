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
import type { components } from "../types/api";
import { getNavConfig } from "../utils/navConfig";

type SpeciesOut = components["schemas"]["SpeciesOut"];
type DatasetOut = components["schemas"]["DatasetOut"];
type AreaOut = components["schemas"]["AreaOut"];
type BasisOfRecordOut = components["schemas"]["BasisOfRecordOut"];


const { t } = useI18n();
const filtersStore = useFiltersStore();

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
</script>

<template>
    <div class="filter-bar">
        <!-- Species -->
        <div class="filter-group">
            <label>{{ t("message.species") }}</label>
            <SpeciesFilterModal
                v-model="selectedSpeciesIds"
                :options="speciesOptions"
            />
        </div>

        <!-- Datasets -->
        <div class="filter-group">
            <label>{{ t("message.dataset") }}</label>
            <DatasetFilterModal
                v-model="selectedDatasetIds"
                :options="datasetOptions"
            />
        </div>

        <!-- Areas -->
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
                class="filter-control"
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
                class="filter-control"
                style="width: 100px"
            />
        </div>

        <!-- Basis of record -->
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
                class="filter-control"
            />
        </div>

        <!-- Start date -->
        <div class="filter-group">
            <label>{{ t("message.date") }} (from)</label>
            <DatePicker
                v-model="startDateObj"
                date-format="yy-mm-dd"
                show-button-bar
                class="filter-control"
            />
        </div>

        <!-- End date -->
        <div class="filter-group">
            <label>{{ t("message.date") }} (to)</label>
            <DatePicker
                v-model="endDateObj"
                date-format="yy-mm-dd"
                show-button-bar
                class="filter-control"
            />
        </div>

        <!-- Verification filter -->
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
</template>

<style scoped>
.filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: flex-end;
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.filter-group label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--p-text-muted-color);
    white-space: nowrap;
}

.filter-control {
    min-width: 150px;
    max-width: 200px;
}

/* Make the modal trigger buttons look consistent with the Select controls */
:deep(.filter-modal-trigger) {
    min-width: 150px;
    max-width: 200px;
    justify-content: flex-start;
}

.status-count-badge {
    display: inline-block;
    margin-left: 0.4em;
    padding: 0 0.45em;
    border-radius: 999px;
    font-size: 0.75em;
    font-weight: 700;
    line-height: 1.6;
    /* Default (inactive): subtle outline */
    background: transparent;
    border: 1px solid currentColor;
    opacity: 0.7;
}

/* On an active (coloured) button: solid white pill with dark text */
:deep(.status-select-button .p-togglebutton-checked .status-count-badge) {
    background: rgba(255, 255, 255, 0.9) !important;
    color: #333 !important;
    border: none;
    opacity: 1;
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


</style>
