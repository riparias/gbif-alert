<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useFiltersStore } from "../stores/filters";
import ObservationHistogram from "./ObservationHistogram.vue";

const { t } = useI18n();
const filtersStore = useFiltersStore();

function isoDate(d: Date): string {
    return d.toISOString().substring(0, 10);
}

function yearMonth(iso: string): string {
    return iso.substring(0, 7); // "YYYY-MM"
}

function lastMonthDate(): Date {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d;
}

function lastYearDate(): Date {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return d;
}

const lastMonthActive = computed(() =>
    filtersStore.endDate === null &&
    filtersStore.startDate !== null &&
    yearMonth(filtersStore.startDate) === yearMonth(isoDate(lastMonthDate()))
);

const lastYearActive = computed(() =>
    filtersStore.endDate === null &&
    filtersStore.startDate !== null &&
    yearMonth(filtersStore.startDate) === yearMonth(isoDate(lastYearDate()))
);

function applyLastMonth(): void {
    filtersStore.startDate = isoDate(lastMonthDate());
    filtersStore.endDate = null;
}

function applyLastYear(): void {
    filtersStore.startDate = isoDate(lastYearDate());
    filtersStore.endDate = null;
}
</script>

<template>
    <div class="histogram-brush">
        <div class="brush-header">
            <span class="brush-label">{{ t("message.observationsOverTime") }}</span>
            <div class="brush-presets">
                <button
                    class="brush-preset"
                    :class="{ 'is-active': lastMonthActive }"
                    @click="applyLastMonth"
                >
                    {{ t("message.lastMonth") }}
                </button>
                <button
                    class="brush-preset"
                    :class="{ 'is-active': lastYearActive }"
                    @click="applyLastYear"
                >
                    {{ t("message.lastYear") }}
                </button>
            </div>
        </div>
        <div class="brush-body">
            <ObservationHistogram :height="90" full-range />
        </div>
    </div>
</template>

<style scoped>
.histogram-brush {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    width: 45%;
    margin-left: auto;
}

.brush-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0.25rem;
}

.brush-label {
    font-size: 0.78rem;
    color: var(--p-text-muted-color);
    font-style: italic;
}

.brush-presets {
    display: flex;
    gap: 0.35rem;
}

.brush-preset {
    font-size: 0.78rem;
    font-weight: 600;
    background: transparent;
    color: var(--p-text-muted-color);
    border: 1px solid var(--p-surface-border);
    border-radius: 999px;
    padding: 0.1rem 0.6rem;
    cursor: pointer;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
    font-family: inherit;
    line-height: 1.4;
}

.brush-preset:hover,
.brush-preset.is-active {
    background: var(--p-primary-100, #d1fae5);
    color: var(--p-primary-700, #065f46);
    border-color: var(--p-primary-300, #6ee7b7);
}
</style>
