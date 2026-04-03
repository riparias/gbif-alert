<script setup lang="ts">
import { computed } from "vue";
import { useFiltersStore } from "../stores/filters";
import ObservationHistogram from "./ObservationHistogram.vue";

const filtersStore = useFiltersStore();

// Derive a human-readable date range label from the active date filters.
// When no dates are set, show "All dates".
const dateRangeLabel = computed(() => {
    const start = filtersStore.startDate ? filtersStore.startDate.substring(0, 4) : null;
    const end = filtersStore.endDate ? filtersStore.endDate.substring(0, 4) : null;
    if (start && end) return `${start} - ${end}`;
    if (start) return `From ${start}`;
    if (end) return `Until ${end}`;
    return "All dates";
});
</script>

<template>
    <div class="histogram-brush">
        <div class="brush-header">
            <span class="brush-label">Timeline - drag to filter</span>
            <span class="brush-pill">{{ dateRangeLabel }}</span>
        </div>
        <div class="brush-body">
            <ObservationHistogram :height="90" />
            <!-- Static selection overlay (stub - not interactive yet) -->
            <div class="brush-overlay" aria-hidden="true" />
        </div>
    </div>
</template>

<style scoped>
.histogram-brush {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
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

.brush-pill {
    font-size: 0.78rem;
    font-weight: 600;
    background: var(--p-primary-100, #d1fae5);
    color: var(--p-primary-700, #065f46);
    border: 1px solid var(--p-primary-300, #6ee7b7);
    border-radius: 999px;
    padding: 0.1rem 0.6rem;
}

.brush-body {
    position: relative;
}

/* Static teal selection overlay spanning the rightmost ~38% of the chart.
   This is a visual stub - the position does not correspond to actual dates. */
.brush-overlay {
    position: absolute;
    top: 0;
    left: 62%;
    right: 0;
    bottom: 25px; /* leave room for x-axis labels */
    background: var(--p-primary-500, #00a58d);
    opacity: 0.15;
    pointer-events: none;
    border-radius: 2px;
}
</style>
