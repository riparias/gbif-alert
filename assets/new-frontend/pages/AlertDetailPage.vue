<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import Card from "primevue/card";
import SelectButton from "primevue/selectbutton";
import ObservationsView from "../components/ObservationsView.vue";
import type { components } from "../types/api";
import { useFiltersStore } from "../stores/filters";

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

// Status options for the toggle; actual state lives in filtersStore.status
const statusOptions = [
    { label: t("message.unseen"), value: "unseen" as const },
    { label: t("message.all"), value: null as null },
];

function getCsrf(): string {
    return (document.cookie.match(/csrftoken=([^;]+)/) ?? [])[1] ?? "";
}

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
                    <ul class="alert-details-list">
                        <li>
                            <b>{{ t("message.species") }}:</b> {{ alert.speciesList }}
                        </li>
                        <li>
                            <b>{{ t("message.area") }}:</b>
                            {{ alert.areaDescription || t("message.everywhere") }}
                        </li>
                        <li v-if="alert.datasetsList">
                            <b>{{ t("message.dataset") }}:</b> {{ alert.datasetsList }}
                        </li>
                        <li v-if="alert.basisOfRecordList">
                            <b>{{ t("message.basisOfRecord") }}:</b>
                            {{ alert.basisOfRecordList }}
                        </li>
                        <li>
                            <b>{{ t("message.verificationFilter") }}:</b>
                            {{ alert.verifiedFilterDisplay }}
                        </li>
                    </ul>
                </template>
            </Card>

            <!-- Status toggle: mutates filtersStore.status; ObservationsView watches it and reloads -->
            <SelectButton
                :model-value="filtersStore.status"
                :options="statusOptions"
                option-label="label"
                option-value="value"
                :allow-empty="false"
                @update:model-value="(v) => (filtersStore.status = v)"
            />

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

.alert-details-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
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
