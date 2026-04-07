<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Dialog from "primevue/dialog";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import type { components } from "../types/api";

type DatasetOut = components["schemas"]["DatasetOut"];

const props = defineProps<{
    modelValue: number[];
    options: DatasetOut[];
}>();

const emit = defineEmits<{
    "update:modelValue": [ids: number[]];
}>();

const { t } = useI18n();

const visible = ref(false);
const search = ref("");

const localIds = ref(new Set(props.modelValue));
watch(
    () => props.modelValue,
    (ids) => { localIds.value = new Set(ids); },
    { deep: true }
);

const filtered = computed(() => {
    const q = search.value.trim().toLowerCase();
    if (!q) return props.options;
    return props.options.filter((d) => d.name.toLowerCase().includes(q));
});

const tableSelection = computed(() =>
    filtered.value.filter((d) => localIds.value.has(d.id))
);

const buttonLabel = computed(() =>
    props.modelValue.length
        ? `${props.modelValue.length} ${t("message.xSelectedDatasets")}`
        : t("message.allDatasets")
);

function onRowSelect(e: { data: DatasetOut }) {
    localIds.value = new Set([...localIds.value, e.data.id]);
    emit("update:modelValue", [...localIds.value]);
}

function onRowUnselect(e: { data: DatasetOut }) {
    const next = new Set(localIds.value);
    next.delete(e.data.id);
    localIds.value = next;
    emit("update:modelValue", [...next]);
}

function onSelectAll() {
    localIds.value = new Set([...localIds.value, ...filtered.value.map((d) => d.id)]);
    emit("update:modelValue", [...localIds.value]);
}

function onUnselectAll() {
    const filteredIds = new Set(filtered.value.map((d) => d.id));
    localIds.value = new Set([...localIds.value].filter((id) => !filteredIds.has(id)));
    emit("update:modelValue", [...localIds.value]);
}
</script>

<template>
    <Button
        :label="buttonLabel"
        size="small"
        outlined
        class="filter-modal-trigger"
        @click="visible = true"
    />

    <Dialog
        v-model:visible="visible"
        :header="t('message.datasetsToInclude')"
        modal
        :style="{ width: '960px', maxWidth: '95vw' }"
    >
        <!-- Search + count -->
        <div class="search-row">
            <InputText
                v-model="search"
                :placeholder="t('message.typeHereToFilter')"
                size="small"
                class="dataset-search"
            />
            <span class="entry-count">
                {{ t("message.selectedEntries") }}{{ modelValue.length }}/{{ options.length }}
            </span>
        </div>

        <!-- Datasets table -->
        <DataTable
            :value="filtered"
            :selection="tableSelection"
            selection-mode="multiple"
            data-key="id"
            scrollable
            scroll-height="65vh"
            size="small"
            @row-select="onRowSelect"
            @row-unselect="onRowUnselect"
            @row-select-all="onSelectAll"
            @row-unselect-all="onUnselectAll"
        >
            <Column selection-mode="multiple" style="width: 2.5rem" />
            <Column field="name" :header="t('message.name')" sortable />
            <Column :header="t('message.gbifDatasetKey')">
                <template #body="{ data }">
                    <a
                        v-if="data.gbifKey"
                        :href="`https://www.gbif.org/dataset/${data.gbifKey}`"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="gbif-link"
                    >{{ data.gbifKey }}</a>
                </template>
            </Column>
        </DataTable>
    </Dialog>
</template>

<style scoped>
.search-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
}

.dataset-search {
    flex: 1;
}

.entry-count {
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
    white-space: nowrap;
}

.gbif-link {
    color: var(--p-primary-color);
    font-size: 0.85rem;
}
</style>
