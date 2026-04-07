<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import AlertSidebar from "../components/AlertSidebar.vue";
import ObservationsView from "../components/ObservationsView.vue";
import type { components } from "../types/api";
import { useFiltersStore } from "../stores/filters";
import { getNavConfig } from "../utils/navConfig";

type AlertOut = components["schemas"]["AlertOut"];

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const filtersStore = useFiltersStore();

const alertId = Number(route.params.alertId);

const alert = ref<AlertOut | null>(null);
const alertLoading = ref(false);
const alertNotFound = ref(false);

const navConfig = getNavConfig();

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
    filtersStore.$reset();
});
</script>

<template>
    <div v-if="alertLoading" class="loading-placeholder">
        <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem" />
    </div>

    <div v-else-if="alertNotFound" class="not-found">
        <p>{{ t("message.alertDetails") }} - {{ t("message.observationNotFound") }}</p>
        <Button :label="t('message.backToAlertsList')" @click="router.push('/my-alerts')" />
    </div>

    <div v-else-if="alert" class="alert-detail-layout">
        <aside class="alert-detail-sidebar">
            <AlertSidebar :alert="alert" />
        </aside>

        <div class="alert-detail-main">
            <ObservationsView :unseen-fallback="true" />
        </div>
    </div>
</template>

<style scoped>
.alert-detail-layout {
    display: grid;
    grid-template-columns: 310px 1fr;
    gap: 1rem;
    padding: 1rem;
    min-height: 0;
}

.alert-detail-sidebar {
    position: sticky;
    top: 1rem;
    height: fit-content;
    background: #1e293b;
    overflow: hidden;
}

.alert-detail-main {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 0;
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
