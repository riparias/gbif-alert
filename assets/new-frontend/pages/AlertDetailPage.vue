<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import Card from "primevue/card";
import Tag from "primevue/tag";
import ObservationsView from "../components/ObservationsView.vue";
import ObservationStatusToggle from "../components/ObservationStatusToggle.vue";
import type { components } from "../types/api";
import { useFiltersStore } from "../stores/filters";
import { getCsrf } from "../utils/csrf";
import { useAlertMeta } from "../composables/useAlertMeta";

type AlertOut = components["schemas"]["AlertOut"];

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const confirm = useConfirm();
const filtersStore = useFiltersStore();

const alertId = Number(route.params.alertId);

const alert = ref<AlertOut | null>(null);
const alertLoading = ref(false);
const alertNotFound = ref(false);

// alertMeta is only used once alert is loaded; the template guards with v-else-if="alert"
const { speciesExpanded, tooManySpecies, visibleSpecies, areaDescription } = useAlertMeta(
    () => alert.value!
);

function confirmDelete() {
    confirm.require({
        message: t("message.alertDeletionConfirmationMessage"),
        header: alert.value?.name ?? "",
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: async () => {
            await fetch(`/api/v2/alerts/${alertId}/`, {
                method: "DELETE",
                headers: { "X-CSRFToken": getCsrf() },
            });
            router.push("/my-alerts");
        },
    });
}

const navConfig = JSON.parse(
    document.getElementById("gbif-alert-nav-config")!.textContent!
);

onMounted(async () => {
    alertLoading.value = true;
    try {
        const res = await fetch(`/api/v2/alerts/${alertId}/`);
        if (!res.ok) {
            alertNotFound.value = true;
            return;
        }
        alert.value = await res.json();
        document.title = `${alert.value!.name} - ${navConfig.siteName}`;
        // Patch Pinia with the alert's pre-configured filters before ObservationsView mounts.
        // filtersStore.status starts as "unseen" (Pinia default) - the toggle below owns it.
        filtersStore.$patch({
            speciesIds: alert.value!.speciesIds,
            datasetsIds: alert.value!.datasetIds,
            basisOfRecordIds: alert.value!.basisOfRecordIds,
            areaIds: alert.value!.areaIds,
            verifiedFilter: alert.value!.verifiedFilter as "all" | "verified" | "unverified",
            areaFilterMode: alert.value!.areaFilterMode as "inside" | "approaching" | "both",
            approachingDistanceKm: alert.value!.approachingDistanceKm,
            startDate: null,
            endDate: null,
            status: "unseen",
        });
    } finally {
        alertLoading.value = false;
    }
});

onUnmounted(() => {
    // Restore Pinia defaults so returning to IndexPage starts fresh.
    filtersStore.$reset();
});
</script>

<template>
    <div class="alert-detail-page">
        <div v-if="alertLoading" class="loading-placeholder">
            <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem" />
        </div>

        <div v-else-if="alertNotFound" class="not-found">
            <p>{{ t("message.alertDetails") }} - {{ t("message.observationNotFound") }}</p>
            <Button :label="t('message.backToAlertsList')" @click="router.push('/my-alerts')" />
        </div>

        <template v-else-if="alert">
            <!-- Alert metadata card -->
            <Card>
                <template #title>
                    <div class="alert-header">
                        <span>{{ alert.name }}</span>
                        <div class="alert-header-actions">
                            <Button
                                :label="t('message.editThisAlert')"
                                icon="pi pi-pencil"
                                size="small"
                                severity="secondary"
                                @click="router.push(`/edit-alert/${alert.id}`)"
                            />
                            <Button
                                :label="t('message.deleteThisAlert')"
                                icon="pi pi-trash"
                                size="small"
                                severity="danger"
                                outlined
                                @click="confirmDelete"
                            />
                        </div>
                    </div>
                </template>
                <template #content>
                    <div class="alert-meta">
                        <!-- Species -->
                        <div class="meta-section">
                            <ul class="species-list">
                                <li v-for="sp in visibleSpecies" :key="sp.scientificName">
                                    <em>{{ sp.scientificName }}</em>
                                    <span v-if="sp.vernacularName" class="vernacular-name">
                                        ({{ sp.vernacularName }})
                                    </span>
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
                                        : `${alert.speciesDetails.length - 4} ${t("message.more")}...`
                                }}
                            </button>
                        </div>

                        <!-- Area -->
                        <div class="meta-row">
                            <i class="pi pi-map-marker meta-icon" />
                            <span :class="{ muted: !areaDescription }">
                                {{ areaDescription || t("message.everywhere") }}
                            </span>
                        </div>

                        <!-- Datasets -->
                        <div v-if="alert.datasetNames.length > 0" class="meta-row chips-row">
                            <i class="pi pi-database meta-icon" />
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

                        <!-- Basis of record -->
                        <div v-if="alert.basisOfRecordList" class="meta-row">
                            <i class="pi pi-tag meta-icon" />
                            <span>{{ alert.basisOfRecordList }}</span>
                        </div>

                        <!-- Verification filter (hidden when "all" - no restriction applied) -->
                        <div v-if="alert.verifiedFilter !== 'all'" class="meta-row">
                            <i class="pi pi-check-circle meta-icon" />
                            <span>{{
                                alert.verifiedFilter === "verified"
                                    ? t("message.verifiedOnly")
                                    : t("message.unverifiedOnly")
                            }}</span>
                        </div>
                    </div>
                </template>
            </Card>

            <!-- Status toggle: mutates filtersStore.status; ObservationsView watches it and reloads -->
            <ObservationStatusToggle />

            <!-- Full observation experience (counter, histogram, map, table, drawer).
                 v-if ensures Pinia is already patched when this component mounts. -->
            <ObservationsView :unseen-fallback="true" />
        </template>
    </div>
</template>

<style scoped>
.alert-detail-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
}

.alert-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.alert-header-actions {
    display: flex;
    gap: 0.5rem;
}

.alert-meta {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.meta-section {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
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
}

.vernacular-name {
    color: var(--p-text-muted-color);
    font-size: 0.875rem;
    margin-left: 0.25rem;
}

.expand-toggle {
    all: unset;
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--p-primary-color);
    margin-top: 0.2rem;
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

.chips-row {
    align-items: flex-start;
}

.chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.dataset-chip {
    font-size: 0.75rem;
}

.loading-placeholder,
.not-found {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 3rem;
    color: var(--p-text-muted-color);
}
</style>
