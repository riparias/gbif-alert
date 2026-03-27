<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, type ObjectDirective, type DirectiveBinding, ref } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import { scaleBand, scaleLinear } from "d3-scale";
import { max } from "d3-array";
import { axisLeft, axisBottom, format, select } from "d3";
import { useFiltersStore } from "../stores/filters";

const { t } = useI18n();
const filtersStore = useFiltersStore();

// --- Types ---

interface HistogramEntry {
    year: number;
    month: number;
    count: number;
}

interface BarEntry {
    yearMonth: string; // "YYYY-M"
    count: number;
}

// --- Data fetching ---

const rawData = ref<HistogramEntry[]>([]);
const loading = ref(false);

function buildFilterParams(): URLSearchParams {
    const params = new URLSearchParams();
    for (const id of filtersStore.speciesIds) params.append("speciesIds", String(id));
    for (const id of filtersStore.datasetsIds) params.append("datasetsIds", String(id));
    for (const id of filtersStore.areaIds) params.append("areaIds", String(id));
    for (const id of filtersStore.basisOfRecordIds) {
        params.append("basisOfRecordIds", String(id));
    }
    if (filtersStore.status) params.set("status", filtersStore.status);
    params.set("verifiedFilter", filtersStore.verifiedFilter);
    params.set("areaFilterMode", filtersStore.areaFilterMode);
    if (filtersStore.approachingDistanceKm !== null) {
        params.set("approachingDistanceKm", String(filtersStore.approachingDistanceKm));
    }
    // startDate and endDate are intentionally omitted: the backend ignores them
    // for the histogram, and we avoid sending unnecessary params.
    return params;
}

async function loadHistogram() {
    loading.value = true;
    try {
        const response = await fetch(`/api/v2/observations/histogram/?${buildFilterParams()}`);
        rawData.value = await response.json();
    } finally {
        loading.value = false;
    }
}

const debouncedReload = debounce(loadHistogram, 300);
watch(filtersStore, debouncedReload, { deep: true });

// --- Data preparation ---

// Build a complete month series from first data month to the current month,
// filling months with no data as 0. This produces a continuous x-axis.
function buildCompleteSeries(data: HistogramEntry[]): BarEntry[] {
    if (data.length === 0) return [];

    const now = new Date();
    const lookup = new Map(data.map((d) => [`${d.year}-${d.month}`, d.count]));
    const result: BarEntry[] = [];

    let y = data[0].year;
    let m = data[0].month;
    const endY = now.getFullYear();
    const endM = now.getMonth() + 1;

    while (y < endY || (y === endY && m <= endM)) {
        const key = `${y}-${m}`;
        result.push({ yearMonth: key, count: lookup.get(key) ?? 0 });
        m++;
        if (m > 12) {
            m = 1;
            y++;
        }
    }

    return result;
}

const barData = computed(() => buildCompleteSeries(rawData.value));
const isEmpty = computed(() => barData.value.every((b) => b.count === 0));

// --- D3 scales ---

const SVG_H = 160;
const M = { top: 10, right: 20, bottom: 25, left: 40 };
const innerH = SVG_H - M.top - M.bottom;

// containerWidth is kept in sync with the wrapper element via ResizeObserver.
// Using real pixel dimensions (instead of viewBox scaling) ensures axis text
// stays at a consistent font size regardless of how wide the container is.
const wrapperEl = ref<HTMLElement | null>(null);
const containerWidth = ref(700);
const innerW = computed(() => containerWidth.value - M.left - M.right);

let resizeObserver: ResizeObserver | null = null;

const xScale = computed(() =>
    scaleBand<string>()
        .domain(barData.value.map((d) => d.yearMonth))
        .range([0, innerW.value])
        .paddingInner(0.3)
);

const yMax = computed(() => max(barData.value, (d) => d.count) ?? 0);

const yScale = computed(() =>
    scaleLinear().domain([0, yMax.value]).range([innerH, 0]).nice()
);

// --- D3 axis directives ---
// Vue directives let D3 draw axes into SVG <g> elements while Vue owns the DOM.

const NUM_X_TICKS = 12;

function applyYAxis(el: SVGGElement, binding: DirectiveBinding) {
    const scale = binding.value.scale;
    const ticks = scale.ticks(4).filter((t: number) => Number.isInteger(t));
    axisLeft<number>(scale).tickValues(ticks).tickFormat(format("d"))(select(el));
}

function applyXAxis(el: SVGGElement, binding: DirectiveBinding) {
    const scale = binding.value.scale;
    const domain: string[] = scale.domain();
    const step = Math.max(1, Math.floor(domain.length / NUM_X_TICKS));
    axisBottom<string>(scale).tickValues(
        domain.filter((_: string, i: number) => i % step === 0)
    )(select(el));
}

const vYaxis: ObjectDirective<SVGGElement> = {
    mounted: applyYAxis,
    updated: applyYAxis,
};

const vXaxis: ObjectDirective<SVGGElement> = {
    mounted: applyXAxis,
    updated: applyXAxis,
};

onMounted(() => {
    loadHistogram();
    if (wrapperEl.value) {
        resizeObserver = new ResizeObserver((entries) => {
            const width = entries[0]?.contentRect.width;
            if (width) containerWidth.value = width;
        });
        resizeObserver.observe(wrapperEl.value);
    }
});

onUnmounted(() => {
    resizeObserver?.disconnect();
});
</script>

<template>
    <div ref="wrapperEl" class="histogram-wrapper">
        <div v-if="!loading && isEmpty" class="histogram-empty">
            {{ t("message.noDataToShowInHistogram") }}
        </div>

        <svg
            v-else
            :width="containerWidth"
            :height="SVG_H"
            class="histogram-svg"
            aria-hidden="true"
        >
            <g :transform="`translate(${M.left}, ${M.top})`">
                <rect
                    v-for="bar in barData"
                    :key="bar.yearMonth"
                    :x="xScale(bar.yearMonth)"
                    :y="yScale(bar.count)"
                    :width="xScale.bandwidth()"
                    :height="innerH - yScale(bar.count)"
                    class="histogram-bar"
                />
                <g v-yaxis="{ scale: yScale }" />
                <g
                    :transform="`translate(0, ${innerH})`"
                    v-xaxis="{ scale: xScale }"
                />
            </g>
        </svg>
    </div>
</template>

<style scoped>
.histogram-wrapper {
    width: 100%;
}

.histogram-svg {
    display: block;
}

.histogram-bar {
    fill: var(--p-primary-500, #00a58d);
    opacity: 0.75;
}

.histogram-empty {
    color: var(--p-text-muted-color);
    font-style: italic;
    padding: 0.5rem 0;
}
</style>
