<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import Tag from "primevue/tag";
import ObservationStatusToggle from "./ObservationStatusToggle.vue";
import { useAlertMeta } from "../composables/useAlertMeta";
import { useResultsStore } from "../stores/results";
import { getCsrf } from "../utils/csrf";
import type { components } from "../types/api";
import { getNavConfig } from "../utils/navConfig";

type AlertOut = components["schemas"]["AlertOut"];

const props = defineProps<{
    alert: AlertOut;
}>();

const { t } = useI18n();
const router = useRouter();
const isAuthenticated: boolean = getNavConfig().user.isAuthenticated;
const confirm = useConfirm();
const resultsStore = useResultsStore();

const { speciesExpanded, tooManySpecies, visibleSpecies, areaDescription, SPECIES_COLLAPSE_THRESHOLD } =
    useAlertMeta(() => props.alert);

function confirmDelete() {
    confirm.require({
        message: t("message.alertDeletionConfirmationMessage"),
        header: props.alert.name,
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: async () => {
            await fetch(`/api/v2/alerts/${props.alert.id}/`, {
                method: "DELETE",
                headers: { "X-CSRFToken": getCsrf() },
            });
            router.push("/my-alerts");
        },
    });
}

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
    <div class="alert-sidebar-panel">
        <!-- Alert name as heading -->
        <div class="sidebar-name">{{ alert.name }}</div>

        <!-- SPECIES section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading"><i class="pi pi-search" />{{ t("message.filterSectionWhat") }}</div>
            <ul class="species-list">
                <li v-for="sp in visibleSpecies" :key="sp.scientificName">
                    <em>{{ sp.scientificName }}</em>
                    <span v-if="sp.vernacularName" class="vernacular-name"> ({{ sp.vernacularName }})</span>
                </li>
            </ul>
            <button
                v-if="tooManySpecies"
                class="expand-toggle"
                @click="speciesExpanded = !speciesExpanded"
            >
                <i :class="speciesExpanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" />
                {{
                    speciesExpanded
                        ? t("message.showLess")
                        : `${alert.speciesDetails.length - SPECIES_COLLAPSE_THRESHOLD} ${t("message.more")}...`
                }}
            </button>
        </div>

        <!-- WHERE section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading"><i class="pi pi-map-marker" />{{ t("message.filterSectionWhere") }}</div>
            <div class="meta-row">
                <i class="pi pi-map-marker meta-icon" />
                <span :class="{ muted: !areaDescription }">
                    {{ areaDescription || t("message.everywhere") }}
                </span>
            </div>
        </div>

        <!-- DATASETS section (hidden when no datasets configured) -->
        <div v-if="alert.datasetNames.length > 0" class="sidebar-section">
            <div class="sidebar-section-heading"><i class="pi pi-database" />{{ t("message.dataset") }}</div>
            <div class="chips">
                <Tag
                    v-for="name in alert.datasetNames"
                    :key="name"
                    :value="name"
                    severity="secondary"
                    class="dataset-chip"
                />
            </div>
        </div>

        <!-- BASIS OF RECORD section (hidden when all) -->
        <div v-if="alert.basisOfRecordList" class="sidebar-section">
            <div class="sidebar-section-heading"><i class="pi pi-tag" />{{ t("message.basisOfRecord") }}</div>
            <div class="meta-row">
                <i class="pi pi-tag meta-icon" />
                <span>{{ alert.basisOfRecordList }}</span>
            </div>
        </div>

        <!-- STATUS section -->
        <div class="sidebar-section">
            <div class="sidebar-section-heading"><i class="pi pi-check-circle" />{{ t("message.filterSectionStatus") }}</div>
            <div v-if="alert.verifiedFilter !== 'all'" class="meta-row">
                <i class="pi pi-check-circle meta-icon" />
                <span>{{
                    alert.verifiedFilter === "verified"
                        ? t("message.verifiedOnly")
                        : t("message.unverifiedOnly")
                }}</span>
            </div>
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
                    <span class="stat-card-value"><i class="pi pi-list stat-card-icon" />{{ formattedSpeciesCount }}</span>
                    <span class="stat-card-label">{{ t("message.statSpeciesLabel") }}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value"><i class="pi pi-database stat-card-icon" />{{ formattedDatasetsCount }}</span>
                    <span class="stat-card-label">{{ t("message.statDatasetsLabel") }}</span>
                </div>
            </div>
        </div>

        <!-- Edit / Delete buttons -->
        <div v-if="isAuthenticated" class="sidebar-actions">
            <Button
                :label="t('message.editThisAlert')"
                icon="pi pi-pencil"
                size="small"
                severity="secondary"
                class="action-btn"
                @click="router.push(`/edit-alert/${alert.id}`)"
            />
            <Button
                :label="t('message.deleteThisAlert')"
                icon="pi pi-trash"
                size="small"
                severity="danger"
                outlined
                class="action-btn"
                @click="confirmDelete"
            />
        </div>
    </div>
</template>

<style scoped>
.alert-sidebar-panel {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 0.75rem;
    height: 100%;
}

.sidebar-name {
    font-size: 0.95rem;
    font-weight: 700;
    color: #f1f5f9; /* slate-100 */
    line-height: 1.3;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid #334155; /* slate-700 */
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
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: #e2e8f0; /* slate-200 */
    text-transform: uppercase;
}

.sidebar-section-heading .pi {
    font-size: 0.7rem;
    color: #94a3b8; /* slate-400 - slightly muted relative to heading text */
}

.species-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}

.species-list em {
    font-style: italic;
    font-size: 0.82rem;
    color: #cbd5e1; /* slate-300 */
}

.vernacular-name {
    font-size: 0.78rem;
    color: #64748b; /* slate-500 */
}

.expand-toggle {
    all: unset;
    cursor: pointer;
    font-size: 0.78rem;
    color: var(--p-primary-color);
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}

.expand-toggle:hover {
    text-decoration: underline;
}

.meta-row {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: #cbd5e1; /* slate-300 */
}

.meta-icon {
    flex-shrink: 0;
    color: #64748b; /* slate-500 */
    margin-top: 0.15rem;
    font-size: 0.78rem;
}

.muted {
    color: #64748b; /* slate-500 */
}

.chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.dataset-chip {
    font-size: 0.72rem;
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
}

.filter-group label {
    font-size: 0.78rem;
    font-weight: 500;
    color: #64748b; /* slate-500 */
}

.stat-block {
    margin-top: auto;
    border-top: 1px solid #334155;
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
    color: #f1f5f9;
}

.stat-label {
    font-size: 0.8rem;
    color: #64748b;
}

.stat-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
}

.stat-card {
    display: flex;
    flex-direction: column;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    line-height: 1.2;
}

.stat-card-value {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 1.1rem;
    font-weight: 700;
    color: #f1f5f9;
}

.stat-card-icon {
    font-size: 0.8rem;
    color: #94a3b8; /* slate-400 */
}

.stat-card-label {
    font-size: 0.72rem;
    color: #64748b;
}

.sidebar-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding-top: 0.5rem;
}

.action-btn {
    width: 100%;
    justify-content: center;
}
</style>
