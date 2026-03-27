<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import Dialog from "primevue/dialog";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import type { components } from "../types/api";

type SpeciesOut = components["schemas"]["SpeciesOut"];

const props = defineProps<{
    modelValue: number[];
    options: SpeciesOut[];
}>();

const emit = defineEmits<{
    "update:modelValue": [ids: number[]];
}>();

const { t } = useI18n();

const visible = ref(false);
const search = ref("");
const activeTags = ref<string[]>([]);

// Local set of selected IDs - keeps selections alive when the table is filtered.
const localIds = ref(new Set(props.modelValue));
watch(
    () => props.modelValue,
    (ids) => { localIds.value = new Set(ids); },
    { deep: true }
);

const allTags = computed(() => {
    const s = new Set<string>();
    for (const sp of props.options) for (const tag of sp.tags) s.add(tag);
    return [...s].sort();
});

const filtered = computed(() => {
    let list = props.options;
    const q = search.value.trim().toLowerCase();
    if (q) {
        list = list.filter(
            (sp) =>
                sp.scientificName.toLowerCase().includes(q) ||
                (sp.vernacularName ?? "").toLowerCase().includes(q)
        );
    }
    if (activeTags.value.length) {
        list = list.filter((sp) =>
            activeTags.value.every((activeTag) => sp.tags.includes(activeTag))
        );
    }
    return list;
});

// The subset of the current filtered list that is selected (drives checkbox display).
const tableSelection = computed(() =>
    filtered.value.filter((sp) => localIds.value.has(sp.id))
);

const buttonLabel = computed(() =>
    props.modelValue.length
        ? `${props.modelValue.length} ${t("message.xSelectedSpecies")}`
        : t("message.allSpecies")
);

function toggleTag(tag: string) {
    const i = activeTags.value.indexOf(tag);
    if (i >= 0) activeTags.value.splice(i, 1);
    else activeTags.value.push(tag);
}

function onRowSelect(e: { data: SpeciesOut }) {
    localIds.value = new Set([...localIds.value, e.data.id]);
    emit("update:modelValue", [...localIds.value]);
}

function onRowUnselect(e: { data: SpeciesOut }) {
    const next = new Set(localIds.value);
    next.delete(e.data.id);
    localIds.value = next;
    emit("update:modelValue", [...next]);
}

function onSelectAll() {
    localIds.value = new Set([...localIds.value, ...filtered.value.map((sp) => sp.id)]);
    emit("update:modelValue", [...localIds.value]);
}

function onUnselectAll() {
    const filteredIds = new Set(filtered.value.map((sp) => sp.id));
    localIds.value = new Set([...localIds.value].filter((id) => !filteredIds.has(id)));
    emit("update:modelValue", [...localIds.value]);
}

// Deterministic color from tag name so the same tag always gets the same color.
const TAG_PALETTE = [
    "#0b7285", "#7048e8", "#c92a2a", "#e67700", "#2b8a3e",
    "#1864ab", "#a61e4d", "#087f5b", "#862e9c", "#d9480f",
];
function tagColor(name: string): string {
    let h = 0;
    for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) & 0xffff;
    return TAG_PALETTE[h % TAG_PALETTE.length];
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
        :header="t('message.speciesToInclude')"
        modal
        :style="{ width: '1020px', maxWidth: '95vw' }"
    >
        <!-- Tag filter chips -->
        <div v-if="allTags.length" class="tag-filter-row">
            <span class="tag-filter-label">{{ t("message.filterByTags") }}</span>
            <div class="tag-chips">
                <span
                    v-for="tag in allTags"
                    :key="tag"
                    class="tag-chip"
                    :class="{ 'tag-chip--active': activeTags.includes(tag) }"
                    :style="
                        activeTags.includes(tag)
                            ? { backgroundColor: tagColor(tag), color: '#fff', borderColor: tagColor(tag) }
                            : { borderColor: tagColor(tag), color: tagColor(tag) }
                    "
                    @click="toggleTag(tag)"
                >{{ tag }}</span>
            </div>
        </div>

        <!-- Search + selection count -->
        <div class="search-row">
            <InputText
                v-model="search"
                :placeholder="t('message.typeHereToFilter')"
                size="small"
                class="species-search"
            />
            <span class="entry-count">
                {{ t("message.selectedEntries") }}{{ modelValue.length }}/{{ options.length }}
            </span>
        </div>

        <!-- Species table -->
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
            <Column field="scientificName" :header="t('message.scientificName')" sortable>
                <template #body="{ data }"><em>{{ data.scientificName }}</em></template>
            </Column>
            <Column field="vernacularName" :header="t('message.vernacularName')" />
            <Column :header="t('message.gbifTaxonKey')" style="width: 9rem">
                <template #body="{ data }">
                    <a
                        v-if="data.gbifTaxonKey"
                        :href="`https://www.gbif.org/species/${data.gbifTaxonKey}`"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="gbif-link"
                    >{{ data.gbifTaxonKey }}</a>
                </template>
            </Column>
            <Column :header="t('message.tags')">
                <template #body="{ data }">
                    <span
                        v-for="tag in data.tags"
                        :key="tag"
                        class="row-tag"
                        :style="{ backgroundColor: tagColor(tag) }"
                    >{{ tag }}</span>
                </template>
            </Column>
        </DataTable>
    </Dialog>
</template>

<style scoped>
.tag-filter-row {
    margin-bottom: 0.75rem;
}

.tag-filter-label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--p-text-muted-color);
    margin-bottom: 0.4rem;
}

.tag-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.tag-chip {
    cursor: pointer;
    padding: 2px 9px;
    border-radius: 10px;
    border: 1px solid;
    font-size: 0.78rem;
    white-space: nowrap;
    user-select: none;
    transition: background-color 0.15s, color 0.15s;
}

.tag-chip--active {
    font-weight: 600;
}

.search-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
}

.species-search {
    flex: 1;
}

.entry-count {
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
    white-space: nowrap;
}

.gbif-link {
    color: var(--p-primary-color);
}

.row-tag {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 8px;
    font-size: 0.73rem;
    color: #fff;
    font-weight: 500;
    margin: 1px 2px;
    white-space: nowrap;
}
</style>
