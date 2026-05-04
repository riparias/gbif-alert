<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useFiltersStore } from "../stores/filters";
import { useFilterOptionsStore } from "../stores/filterOptions";
import SpeciesName from "./SpeciesName.vue";

const { t } = useI18n();
const filtersStore = useFiltersStore();
const optionsStore = useFilterOptionsStore();

interface BaseChip {
    key: string;
    clear: () => void;
}
interface TextChip extends BaseChip {
    kind: "text";
    label: string;
}
interface SpeciesChip extends BaseChip {
    kind: "species";
    scientificName: string;
    vernacularName: string;
    fallbackLabel: string;  // for the "Species #42" case when the option is unknown
}
type Chip = TextChip | SpeciesChip;

const chips = computed<Chip[]>(() => {
    const result: Chip[] = [];

    // Species
    for (const id of filtersStore.speciesIds) {
        const sp = optionsStore.species.find((s) => s.id === id);
        result.push({
            kind: "species",
            key: `species-${id}`,
            scientificName: sp ? sp.scientificName : "",
            vernacularName: sp ? sp.vernacularName : "",
            fallbackLabel: `Species #${id}`,
            clear: () => {
                filtersStore.speciesIds = filtersStore.speciesIds.filter((i) => i !== id);
            },
        });
    }

    // Datasets
    for (const id of filtersStore.datasetsIds) {
        const ds = optionsStore.datasets.find((d) => d.id === id);
        result.push({
            kind: "text",
            key: `dataset-${id}`,
            label: ds ? ds.name : `Dataset #${id}`,
            clear: () => {
                filtersStore.datasetsIds = filtersStore.datasetsIds.filter((i) => i !== id);
            },
        });
    }

    // Areas
    for (const id of filtersStore.areaIds) {
        const area = optionsStore.areas.find((a) => a.id === id);
        result.push({
            kind: "text",
            key: `area-${id}`,
            label: area ? area.name : `Area #${id}`,
            clear: () => {
                filtersStore.areaIds = filtersStore.areaIds.filter((i) => i !== id);
            },
        });
    }

    // Basis of record
    for (const id of filtersStore.basisOfRecordIds) {
        const bor = optionsStore.basisOfRecord.find((b) => b.id === id);
        result.push({
            kind: "text",
            key: `bor-${id}`,
            label: bor ? bor.name : `Record type #${id}`,
            clear: () => {
                filtersStore.basisOfRecordIds = filtersStore.basisOfRecordIds.filter((i) => i !== id);
            },
        });
    }

    // Date range
    if (filtersStore.startDate) {
        const d = filtersStore.startDate;
        result.push({
            kind: "text",
            key: "start-date",
            label: `${t("message.dateFromPrefix")} ${d}`,
            clear: () => { filtersStore.startDate = null; },
        });
    }
    if (filtersStore.endDate) {
        const d = filtersStore.endDate;
        result.push({
            kind: "text",
            key: "end-date",
            label: `${t("message.dateUntilPrefix")} ${d}`,
            clear: () => { filtersStore.endDate = null; },
        });
    }

    // Verified filter
    if (filtersStore.verifiedFilter !== "all") {
        const label =
            filtersStore.verifiedFilter === "verified"
                ? t("message.verifiedOnly")
                : t("message.unverifiedOnly");
        result.push({
            kind: "text",
            key: "verified",
            label,
            clear: () => { filtersStore.verifiedFilter = "all"; },
        });
    }

    // Observation status
    if (filtersStore.status !== null) {
        const label = filtersStore.status === "unseen" ? t("message.unseen") : t("message.seen");
        result.push({
            kind: "text",
            key: "status",
            label,
            clear: () => { filtersStore.status = null; },
        });
    }

    return result;
});

const hasChips = computed(() => chips.value.length > 0);

function clearAll() {
    filtersStore.speciesIds = [];
    filtersStore.datasetsIds = [];
    filtersStore.areaIds = [];
    filtersStore.basisOfRecordIds = [];
    filtersStore.startDate = null;
    filtersStore.endDate = null;
    filtersStore.verifiedFilter = "all";
    filtersStore.status = null;
}
</script>

<template>
    <div v-if="hasChips" class="active-chips-bar">
        <span class="chips-label">{{ t("message.activeFilters") }}</span>
        <div class="chips-scroll">
            <span
                v-for="chip in chips"
                :key="chip.key"
                class="filter-chip"
            >
                <template v-if="chip.kind === 'species'">
                    <SpeciesName
                        v-if="chip.scientificName"
                        :scientific-name="chip.scientificName"
                        :vernacular-name="chip.vernacularName"
                    />
                    <template v-else>{{ chip.fallbackLabel }}</template>
                    <button
                        class="chip-clear"
                        :aria-label="t('message.removeFilter', { label: chip.scientificName || chip.fallbackLabel })"
                        @click="chip.clear()"
                    >
                        &times;
                    </button>
                </template>
                <template v-else>
                    {{ chip.label }}
                    <button
                        class="chip-clear"
                        :aria-label="t('message.removeFilter', { label: chip.label })"
                        @click="chip.clear()"
                    >
                        &times;
                    </button>
                </template>
            </span>
            <button class="clear-all-btn" @click="clearAll">{{ t("message.clearAllFilters") }}</button>
        </div>
    </div>
</template>

<style scoped>
.active-chips-bar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.4rem 0.65rem;
    background: rgba(37, 99, 235, 0.1);
    border: 1px solid rgba(37, 99, 235, 0.3);
    border-radius: 6px;
}

.chips-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #93c5fd; /* blue-300 */
    white-space: nowrap;
    flex-shrink: 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.chips-scroll {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
}

.filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background: #1e3a5f;
    border: 1px solid #2563eb;
    color: #bfdbfe; /* blue-200 */
    font-size: 0.75rem;
    font-weight: 500;
    border-radius: 999px;
    padding: 0.15rem 0.5rem 0.15rem 0.6rem;
    white-space: nowrap;
}

.chip-clear {
    background: none;
    border: none;
    color: #93c5fd;
    cursor: pointer;
    font-size: 0.9rem;
    line-height: 1;
    padding: 0;
    display: flex;
    align-items: center;
}

.chip-clear:hover {
    color: #fff;
}

.clear-all-btn {
    flex-shrink: 0;
    background: #b91c1c; /* red-700 - solid, readable */
    border: 1px solid #991b1b;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    white-space: nowrap;
}

.clear-all-btn:hover {
    background: #dc2626; /* red-600 */
}
</style>
