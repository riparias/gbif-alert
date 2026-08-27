<script setup lang="ts">
import { useI18n } from "vue-i18n";
import Paginator, { type PageState } from "primevue/paginator";
import Select from "primevue/select";
import SpeciesName from "./SpeciesName.vue";
import { pickVernacular } from "../utils/vernacular";
import { useDisplayLabels } from "../composables/useDisplayLabels";
import type { components } from "../types/api";

type ObservationOut = components["schemas"]["ObservationOut"];

/**
 * The small-screen form of the observations table.
 *
 * A phone cannot show eight columns, and PrimeVue 4 dropped v3's stacked
 * DataTable layout (the `breakpoint` prop survives in the type declarations but
 * nothing reads it), so each observation becomes a tappable card instead. The
 * data, paging and sorting all still belong to ObservationsView - this
 * component only renders and emits.
 *
 * Species comes first because it is what someone triaging an alert scans for;
 * date and municipality answer "is this one I already know about?".
 */
const props = defineProps<{
    observations: ObservationOut[];
    totalRecords: number;
    rows: number;
    /** Zero-based, as PrimeVue's Paginator expects. */
    first: number;
    loading: boolean;
    sortField: string;
    sortOrder: 1 | -1;
    /** Wire-level field name for the species column, per the display preference. */
    speciesSortField: string;
    /** True when any row carries a seen/unseen status (i.e. the user is signed in). */
    hasSeen: boolean;
}>();

const emit = defineEmits<{
    open: [stableId: string];
    page: [event: PageState];
    sort: [field: string, order: 1 | -1];
}>();

const { t, locale } = useI18n();
const { basisOfRecordName } = useDisplayLabels();

// Column headers are the desktop way to sort; on a phone they are gone, so the
// four combinations that actually matter become an explicit list.
type SortChoice = { value: string; label: string; field: "date" | "species"; order: 1 | -1 };

const sortChoices = (): SortChoice[] => [
    { value: "date-desc", label: t("message.sortDateDesc"), field: "date", order: -1 },
    { value: "date-asc", label: t("message.sortDateAsc"), field: "date", order: 1 },
    { value: "species-asc", label: t("message.sortSpeciesAsc"), field: "species", order: 1 },
    { value: "species-desc", label: t("message.sortSpeciesDesc"), field: "species", order: -1 },
];

// The current sort as one of the four choices. The species field name varies
// with the scientific/vernacular preference, hence the comparison against the
// prop rather than a literal.
function currentSortValue(): string {
    const field = props.sortField === "date" ? "date" : "species";
    return `${field}-${props.sortOrder === 1 ? "asc" : "desc"}`;
}

function onSortChange(event: { value: string }): void {
    const choice = sortChoices().find((c) => c.value === event.value);
    if (!choice) return;
    emit("sort", choice.field === "date" ? "date" : props.speciesSortField, choice.order);
}
</script>

<template>
    <div class="obs-card-list">
        <div class="obs-card-list-toolbar">
            <label for="obs-sort" class="obs-sort-label">{{ t("message.sortBy") }}</label>
            <Select
                input-id="obs-sort"
                :model-value="currentSortValue()"
                :options="sortChoices()"
                option-value="value"
                option-label="label"
                size="small"
                class="obs-sort-select"
                @change="onSortChange"
            />
        </div>

        <div v-if="loading" class="obs-card-loading">
            <i class="pi pi-spin pi-spinner" />
        </div>

        <ul v-else class="obs-cards">
            <li v-for="obs in observations" :key="obs.stableId">
                <button type="button" class="obs-card" @click="emit('open', obs.stableId)">
                    <span class="obs-card-species">
                        <SpeciesName
                            :scientific-name="obs.scientificName"
                            :vernacular-name="pickVernacular(obs, locale)"
                        />
                        <span
                            v-if="hasSeen && obs.viewedByCurrentUser === false"
                            class="obs-card-unseen"
                            :title="t('message.unseen')"
                        />
                    </span>

                    <span class="obs-card-meta">
                        <span><i class="pi pi-calendar" /> {{ obs.date }}</span>
                        <span v-if="obs.municipality">
                            <i class="pi pi-map-marker" /> {{ obs.municipality }}
                        </span>
                    </span>

                    <span class="obs-card-footer">
                        <span
                            class="verified-badge"
                            :class="obs.verified ? 'badge-success' : 'badge-danger'"
                        >
                            {{ obs.verified ? t("message.verified") : t("message.unverified") }}
                        </span>
                        <span class="obs-card-dataset">{{
                            basisOfRecordName(obs.basisOfRecordId) || obs.datasetName
                        }}</span>
                    </span>
                </button>
            </li>
        </ul>

        <Paginator
            :rows="rows"
            :total-records="totalRecords"
            :first="first"
            template="PrevPageLink CurrentPageReport NextPageLink"
            @page="(e: PageState) => emit('page', e)"
        />
    </div>
</template>

<style scoped>
.obs-card-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.obs-card-list-toolbar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.obs-sort-label {
    font-size: 0.8rem;
    color: var(--p-text-muted-color);
}

.obs-sort-select {
    flex: 1;
    min-width: 0;
}

.obs-card-loading {
    display: flex;
    justify-content: center;
    padding: 2rem;
    color: var(--p-text-muted-color);
}

.obs-cards {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

/* A button rather than a div: the whole card is the tap target for opening the
 * observation, and a button gets keyboard activation and focus for free. */
.obs-card {
    all: unset;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--p-content-border-color);
    border-radius: 8px;
    background: var(--p-content-background);
    cursor: pointer;
}

.obs-card:hover,
.obs-card:focus-visible {
    border-color: var(--p-primary-color);
}

.obs-card-species {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 1rem;
    font-weight: 600;
}

.obs-card-unseen {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #d97706;
    flex-shrink: 0;
}

.obs-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.85rem;
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
}

.obs-card-meta .pi {
    font-size: 0.75rem;
}

.obs-card-footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.78rem;
    color: var(--p-text-muted-color);
}

.obs-card-dataset {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
</style>
