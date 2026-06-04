<script setup lang="ts">
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Badge from "primevue/badge";
import Card from "primevue/card";
import Tag from "primevue/tag";
import SpeciesName from "./SpeciesName.vue";
import type { components } from "../types/api";
import { getCsrf } from "../utils/csrf";
import { useAlertMeta } from "../composables/useAlertMeta";
import { useDisplayLabels } from "../composables/useDisplayLabels";
import { pickVernacular } from "../utils/vernacular";

type AlertOut = components["schemas"]["AlertOut"];

const props = defineProps<{ alert: AlertOut }>();
const emit = defineEmits<{ deleted: [] }>();

const { t, locale } = useI18n();
const { datasetName, frequencyLabel } = useDisplayLabels();
const router = useRouter();
const confirm = useConfirm();
const toast = useToast();

const { speciesExpanded, tooManySpecies, visibleSpecies, areaDescription, SPECIES_COLLAPSE_THRESHOLD } = useAlertMeta(
    () => props.alert
);

function formatDate(iso: string | null): string {
    if (!iso) return t("message.never");
    return new Date(iso).toLocaleDateString();
}

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
            toast.add({
                severity: "success",
                summary: t("message.alertSuccessfullyDeleted"),
                life: 3000,
            });
            emit("deleted");
        },
    });
}
</script>

<template>
    <Card class="alert-card">
        <template #title>
            <div class="card-title-row">
                <span class="alert-name" @click="router.push(`/alert/${alert.id}`)">
                    {{ alert.name }}
                </span>
                <Badge
                    v-if="alert.unseenCount > 0"
                    :value="alert.unseenCount"
                    severity="danger"
                    class="unseen-badge"
                />
            </div>
        </template>

        <template #content>
            <!-- Species section -->
            <div class="section">
                <ul class="species-list">
                    <li v-for="sp in visibleSpecies" :key="sp.scientificName">
                        <SpeciesName
                            :scientific-name="sp.scientificName"
                            :vernacular-name="pickVernacular(sp, locale)"
                        />
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

            <!-- Area -->
            <div class="section meta-row">
                <i class="pi pi-map-marker meta-icon" />
                <span :class="{ muted: !areaDescription }">
                    {{ areaDescription || t("message.everywhere") }}
                </span>
            </div>

            <!-- Datasets (only when filtered) -->
            <div v-if="alert.datasetIds.length > 0" class="section chips-row">
                <i class="pi pi-database meta-icon" />
                <div class="chips">
                    <Tag
                        v-for="id in alert.datasetIds"
                        :key="id"
                        :value="datasetName(id)"
                        severity="secondary"
                        class="dataset-chip"
                    />
                </div>
            </div>

            <!-- Notifications -->
            <div class="section meta-row">
                <i class="pi pi-bell meta-icon" />
                <span>
                    {{ frequencyLabel(alert.emailNotificationsFrequency) }}
                    &middot;
                    <span class="muted">{{ t("message.lastEmailSentAt") }} {{ formatDate(alert.lastEmailSentAt) }}</span>
                </span>
            </div>
        </template>

        <template #footer>
            <div class="card-actions">
                <Button
                    :label="t('message.viewAlertObservations')"
                    icon="pi pi-chart-bar"
                    size="small"
                    @click="router.push(`/alert/${alert.id}`)"
                />
                <Button
                    :label="t('message.editThisAlert')"
                    icon="pi pi-pencil"
                    severity="secondary"
                    size="small"
                    @click="router.push(`/edit-alert/${alert.id}`)"
                />
                <Button
                    :label="t('message.deleteThisAlert')"
                    icon="pi pi-trash"
                    severity="danger"
                    size="small"
                    outlined
                    @click="confirmDelete"
                />
            </div>
        </template>
    </Card>
</template>

<style scoped>
.alert-card {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.card-title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
}

.alert-name {
    font-size: 1.25rem;
    font-weight: 700;
    cursor: pointer;
    color: var(--p-primary-color);
}

.alert-name:hover {
    text-decoration: underline;
}

.unseen-badge {
    flex-shrink: 0;
}

/* Shared section spacing */
.section {
    margin-bottom: 0.75rem;
}

.section:last-child {
    margin-bottom: 0;
}

/* Species */
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
}

.expand-toggle {
    all: unset;
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--p-primary-color);
    margin-top: 0.35rem;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}

.expand-toggle:hover {
    text-decoration: underline;
}

/* Meta rows */
.meta-row {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.875rem;
}

.meta-icon {
    flex-shrink: 0;
    color: var(--p-text-muted-color);
    margin-top: 0.15rem;
    font-size: 0.8rem;
}

.muted {
    color: var(--p-text-muted-color);
}

/* Dataset chips */
.chips-row {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
}

.chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.dataset-chip {
    font-size: 0.75rem;
}

/* Footer actions */
:deep(.p-card-footer) {
    border-top: 1px solid var(--p-content-border-color);
    padding-top: 0.75rem;
    margin-top: 0.25rem;
}

.card-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
</style>
