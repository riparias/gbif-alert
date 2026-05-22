<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import AlertSidebar from "../components/AlertSidebar.vue";
import ObservationsView from "../components/ObservationsView.vue";
import type { components } from "../types/api";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import { getNavConfig } from "../utils/navConfig";

type AlertOut = components["schemas"]["AlertOut"];

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const filtersStore = useFiltersStore();
const resultsStore = useResultsStore();

const alertId = Number(route.params.alertId);

const alert = ref<AlertOut | null>(null);
const alertLoading = ref(false);
const alertNotFound = ref(false);

const navConfig = getNavConfig();

async function fetchAlert(): Promise<void> {
    const res = await fetch(`/api/v2/alerts/${alertId}/`);
    if (!res.ok) {
        alertNotFound.value = true;
        return;
    }
    alert.value = await res.json();
}

onMounted(async () => {
    alertLoading.value = true;
    try {
        await fetchAlert();
        if (!alert.value) return;
        document.title = `${alert.value.name} - ${navConfig.siteName}`;
        filtersStore.$patch({
            speciesIds: alert.value.speciesIds,
            datasetsIds: alert.value.datasetIds,
            basisOfRecordIds: alert.value.basisOfRecordIds,
            areaIds: alert.value.areaIds,
            verifiedFilter: alert.value.verifiedFilter as "all" | "verified" | "unverified",
            areaFilterMode: alert.value.areaFilterMode as "inside" | "approaching" | "both",
            approachingDistanceKm: alert.value.approachingDistanceKm,
            startDate: null,
            endDate: null,
            status: "unseen",
        });
    } finally {
        alertLoading.value = false;
    }
});

// Re-fetch the alert (for unseenCount, which gates the sidebar bulk action)
// whenever a consumer reports an observation status change.
watch(() => resultsStore.statusEpoch, fetchAlert);

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

    <div v-else-if="alert" class="sidebar-layout">
        <aside class="sidebar-layout__aside">
            <AlertSidebar :alert="alert" />
        </aside>

        <div class="sidebar-layout__main">
            <ObservationsView :unseen-fallback="true" />
        </div>
    </div>
</template>

<style scoped>
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
