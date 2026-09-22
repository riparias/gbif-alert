<script setup lang="ts">
import { toRef } from "vue";
import { useI18n } from "vue-i18n";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import type { components } from "../types/api";
import { useFilteredBreakdown } from "../composables/useFilteredBreakdown";

type DatasetCountOut = components["schemas"]["DatasetCountOut"];

const props = defineProps<{ active: boolean }>();

const { t } = useI18n();

const {
    rows,
    loading,
    error: loadError,
    load,
    share,
} = useFilteredBreakdown<DatasetCountOut>(
    "/api/v2/observations/dataset-breakdown/",
    toRef(props, "active"),
);
</script>

<template>
    <div v-if="loadError" class="breakdown-error">
        {{ t("message.resultsLoadFailed") }}
        <a href="#" class="breakdown-retry" @click.prevent="load()">{{ t("message.retry") }}</a>
    </div>
    <DataTable
        v-else
        :value="rows"
        :loading="loading"
        sort-field="count"
        :sort-order="-1"
        row-hover
        class="dataset-breakdown-table"
    >
        <Column field="name" :header="t('message.dataset')" sortable />
        <Column field="count" :header="t('message.observationCount')" sortable />
        <Column :header="t('message.shareOfResults')">
            <template #body="{ data }">
                <div class="share-cell">
                    <div class="share-track">
                        <div class="share-bar" :style="{ width: `${share(data.count)}%` }" />
                    </div>
                    <span class="share-value">{{ share(data.count).toFixed(1) }}%</span>
                </div>
            </template>
        </Column>
    </DataTable>
</template>

<style scoped>
.breakdown-error {
    padding: 1rem;
    color: var(--p-text-muted-color);
}

.breakdown-retry {
    margin-left: 0.5rem;
}

.share-cell {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.share-track {
    flex: 1;
    min-width: 3rem;
    height: 0.5rem;
    background: var(--p-content-border-color);
    border-radius: 999px;
    overflow: hidden;
}
.share-bar {
    height: 100%;
    background: var(--p-primary-color);
}
.share-value {
    font-variant-numeric: tabular-nums;
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
    min-width: 3.5rem;
    text-align: right;
}
</style>
