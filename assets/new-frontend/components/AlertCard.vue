<script setup lang="ts">
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Badge from "primevue/badge";
import Card from "primevue/card";
import Divider from "primevue/divider";
import type { components } from "../types/api";
import { getCsrf } from "../utils/csrf";

type AlertOut = components["schemas"]["AlertOut"];

const props = defineProps<{ alert: AlertOut }>();
const emit = defineEmits<{ deleted: [] }>();

const { t } = useI18n();
const router = useRouter();
const confirm = useConfirm();
const toast = useToast();

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
            <!-- Species -->
            <ul class="species-list">
                <li v-for="sp in alert.speciesDetails" :key="sp.scientificName">
                    <em>{{ sp.scientificName }}</em>
                    <span v-if="sp.vernacularName" class="vernacular-name">
                        ({{ sp.vernacularName }})
                    </span>
                </li>
            </ul>

            <Divider />

            <!-- Metadata summary -->
            <dl class="alert-meta">
                <dt>{{ t("message.area") }}</dt>
                <dd>{{ alert.areaDescription || t("message.everywhere") }}</dd>

                <template v-if="alert.datasetsList">
                    <dt>{{ t("message.dataset") }}</dt>
                    <dd>{{ alert.datasetsList }}</dd>
                </template>

                <template v-if="alert.basisOfRecordList">
                    <dt>{{ t("message.basisOfRecord") }}</dt>
                    <dd>{{ alert.basisOfRecordList }}</dd>
                </template>

                <dt>{{ t("message.alertNotificationsFrequency") }}</dt>
                <dd>{{ alert.emailNotificationsFrequencyDisplay }}</dd>

                <dt>{{ t("message.lastEmailSentOn") }}</dt>
                <dd>{{ formatDate(alert.lastEmailSentOn) }}</dd>
            </dl>
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

/* Make title slot clickable and styled */
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

/* Species */
.species-list {
    list-style: none;
    margin: 0 0 0 0;
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
    font-size: 0.9rem;
    margin-left: 0.3rem;
}

/* Metadata dl */
.alert-meta {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.2rem 1rem;
    margin: 0;
    font-size: 0.875rem;
}

.alert-meta dt {
    font-weight: 600;
    color: var(--p-text-muted-color);
    white-space: nowrap;
}

.alert-meta dd {
    margin: 0;
}

/* Actions */
.card-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
</style>
