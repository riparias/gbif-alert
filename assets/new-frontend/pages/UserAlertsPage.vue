<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Card from "primevue/card";
import Badge from "primevue/badge";
import type { components } from "../types/api";
import { getCsrf } from "../utils/csrf";

type AlertOut = components["schemas"]["AlertOut"];

const { t } = useI18n();
const router = useRouter();
const confirm = useConfirm();
const toast = useToast();

const alerts = ref<AlertOut[]>([]);
const loading = ref(false);

function formatDate(iso: string | null): string {
    if (!iso) return t("message.never");
    return new Date(iso).toLocaleDateString();
}

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

function confirmDelete(alert: AlertOut) {
    confirm.require({
        message: t("message.alertDeletionConfirmationMessage"),
        header: alert.name,
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: async () => {
            await fetch(`/api/v2/alerts/${alert.id}/`, {
                method: "DELETE",
                headers: { "X-CSRFToken": getCsrf() },
            });
            await loadAlerts();
            toast.add({ severity: "success", summary: t("message.alertSuccessfullyDeleted"), life: 3000 });
        },
    });
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
            <p>{{ t("message.noAlertsConfigured") }}</p>
            <Button :label="t('message.createNewAlert')" @click="router.push('/new-alert')" />
        </div>

        <Card v-for="alert in alerts" :key="alert.id" class="alert-card">
            <template #title>
                <span class="alert-title">{{ alert.name }}</span>
                <Badge
                    v-if="alert.unseenCount > 0"
                    :value="alert.unseenCount"
                    severity="danger"
                    class="alert-unseen-badge"
                />
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
                    <li>
                        <b>{{ t("message.dataset") }}:</b>
                        {{ alert.datasetsList || t("message.allDatasets") }}
                    </li>
                    <li>
                        <b>{{ t("message.basisOfRecord") }}:</b>
                        {{ alert.basisOfRecordList || t("message.allBasisOfRecord") }}
                    </li>
                    <li>
                        <b>{{ t("message.verificationFilter") }}:</b>
                        {{ alert.verifiedFilterDisplay }}
                    </li>
                    <li>
                        <b>{{ t("message.alertNotificationsFrequency") }}:</b>
                        {{ alert.emailNotificationsFrequencyDisplay }}
                    </li>
                    <li>
                        <b>{{ t("message.lastEmailSentOn") }}</b>
                        {{ formatDate(alert.lastEmailSentOn) }}
                    </li>
                </ul>
            </template>
            <template #footer>
                <div class="alert-actions">
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
                        @click="confirmDelete(alert)"
                    />
                </div>
            </template>
        </Card>
    </div>
</template>

<style scoped>
.user-alerts-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
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

.alert-card {
    margin-bottom: 0;
}

.alert-title {
    font-size: 1.1rem;
    font-weight: 600;
}

.alert-unseen-badge {
    margin-left: 0.5rem;
    vertical-align: middle;
}

.alert-details-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.alert-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 3rem 1rem;
    color: var(--p-text-muted-color);
}

.loading-placeholder {
    display: flex;
    justify-content: center;
    padding: 3rem;
    color: var(--p-text-muted-color);
}
</style>
