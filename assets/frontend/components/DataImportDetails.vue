<script setup lang="ts">
import { useI18n } from "vue-i18n";
import type { components } from "../types/api";

type DataImportOut = components["schemas"]["DataImportOut"];

defineProps<{ dataImport: DataImportOut }>();

const { t, locale } = useI18n();

function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString(locale.value);
}
</script>

<template>
    <dl class="data-import-details">
        <dt>{{ t("message.dateTimeRange") }}</dt>
        <dd>
            {{ formatDateTime(dataImport.startedAt) }}
            <template v-if="dataImport.endedAt">
                &ndash; {{ formatDateTime(dataImport.endedAt) }}
            </template>
        </dd>

        <dt>{{ t("message.importedObservations") }}</dt>
        <dd>{{ dataImport.importedCount.toLocaleString(locale) }}</dd>

        <dt>{{ t("message.newObservationsThisImport") }}</dt>
        <dd>{{ dataImport.newObservationsCount.toLocaleString(locale) }}</dd>

        <dt>{{ t("message.skippedObservations") }}</dt>
        <dd>{{ dataImport.skippedCount.toLocaleString(locale) }}</dd>
    </dl>
</template>

<style scoped>
.data-import-details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1.5rem;
    margin: 0;
}

.data-import-details dt {
    font-weight: 600;
}

.data-import-details dd {
    margin: 0;
}
</style>
