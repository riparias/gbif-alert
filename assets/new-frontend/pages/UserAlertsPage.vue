<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import Button from "primevue/button";
import AlertCard from "../components/AlertCard.vue";
import type { components } from "../types/api";

type AlertOut = components["schemas"]["AlertOut"];

const { t } = useI18n();
const router = useRouter();

const alerts = ref<AlertOut[]>([]);
const loading = ref(false);

async function loadAlerts() {
    loading.value = true;
    try {
        const res = await fetch("/api/v2/alerts/");
        if (!res.ok) return;
        alerts.value = await res.json();
    } finally {
        loading.value = false;
    }
}

const navConfig = JSON.parse(
    document.getElementById("gbif-alert-nav-config")!.textContent!
);
document.title = `${t("message.navMyAlerts")} - ${navConfig.siteName}`;

onMounted(loadAlerts);
</script>

<template>
    <div class="user-alerts-page">
        <div class="page-header">
            <h1>{{ t("message.navMyAlerts") }}</h1>
            <Button
                icon="pi pi-plus"
                :label="t('message.createNewAlert')"
                @click="router.push('/new-alert')"
            />
        </div>

        <div v-if="loading" class="loading-placeholder">
            <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem" />
        </div>

        <div v-else-if="alerts.length === 0" class="empty-state">
            <i class="pi pi-bell-slash" style="font-size: 2.5rem; color: var(--p-text-muted-color)" />
            <p>{{ t("message.noAlertsConfigured") }}</p>
            <Button
                icon="pi pi-plus"
                :label="t('message.createNewAlert')"
                @click="router.push('/new-alert')"
            />
        </div>

        <div v-else class="alerts-grid">
            <AlertCard
                v-for="alert in alerts"
                :key="alert.id"
                :alert="alert"
                @deleted="loadAlerts"
            />
        </div>
    </div>
</template>

<style scoped>
.user-alerts-page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding: 1rem;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.page-header h1 {
    margin: 0;
}

.alerts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 1.25rem;
    align-items: start;
}

.loading-placeholder {
    display: flex;
    justify-content: center;
    padding: 3rem;
    color: var(--p-text-muted-color);
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 3rem 1rem;
    color: var(--p-text-muted-color);
}
</style>
