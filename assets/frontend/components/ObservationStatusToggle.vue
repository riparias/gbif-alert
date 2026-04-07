<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import SelectButton from "primevue/selectbutton";
import { useFiltersStore } from "../stores/filters";

const { t } = useI18n();
const filtersStore = useFiltersStore();

const statusOptions = [
    { value: "all", label: t("message.all") },
    { value: "seen", label: t("message.seen") },
    { value: "unseen", label: t("message.unseen") },
];

// SelectButton requires non-null values, so we map null <-> "all" at the boundary.
const selectedStatus = computed({
    get: () => filtersStore.status ?? "all",
    set: (val: string) => {
        filtersStore.status = val === "all" ? null : (val as "seen" | "unseen");
    },
});
</script>

<template>
    <div class="status-toggle-wrapper">
        <SelectButton
            v-model="selectedStatus"
            :options="statusOptions"
            option-value="value"
            option-label="label"
            :allow-empty="false"
        />
    </div>
</template>

<style scoped>
/* All (1st) slate, Seen (2nd) green, Unseen (3rd) amber */
:deep(.p-togglebutton:nth-child(1).p-togglebutton-checked),
:deep(.p-togglebutton:nth-child(1).p-togglebutton-checked *) {
    background: #475569;
    border-color: #475569;
    color: #fff;
}

:deep(.p-togglebutton:nth-child(2).p-togglebutton-checked),
:deep(.p-togglebutton:nth-child(2).p-togglebutton-checked *) {
    background: #16a34a;
    border-color: #16a34a;
    color: #fff;
}

:deep(.p-togglebutton:nth-child(3).p-togglebutton-checked),
:deep(.p-togglebutton:nth-child(3).p-togglebutton-checked *) {
    background: #d97706;
    border-color: #d97706;
    color: #fff;
}
</style>
