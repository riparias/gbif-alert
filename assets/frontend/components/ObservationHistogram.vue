<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, type ObjectDirective, type DirectiveBinding, ref } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import { scaleBand, scaleLinear } from "d3-scale";
import { max } from "d3-array";
import { axisLeft, axisBottom, format, select } from "d3";
import { useFiltersStore } from "../stores/filters";
import { useResultsStore } from "../stores/results";
import { filtersToParams } from "../utils/filterParams";

const { t } = useI18n();
const filtersStore = useFiltersStore();
const resultsStore = useResultsStore();

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

// --- Props ---

const props = withDefaults(
    defineProps<{ height?: number; fullRange?: boolean }>(),
    { height: 160, fullRange: false }
);

// --- Data fetching ---

const rawData = ref<HistogramEntry[]>([]);
const loading = ref(false);

function buildFilterParams(): URLSearchParams {
    return filtersToParams(filtersStore, { includeDateRange: !props.fullRange });
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
watch(() => resultsStore.statusEpoch, debouncedReload);

// --- Data preparation ---

function buildCompleteSeries(data: HistogramEntry[]): BarEntry[] {
    if (data.length === 0) return [];

    const now = new Date();
    const lookup = new Map(data.map((d) => [`${d.year}-${d.month}`, d.count]));
    const result: BarEntry[] = [];

    let y = data[0].year;
    let m = data[0].month;
    // fullRange: always extend to current month so the brush shows the full context.
    // filtered: stop at the last data month so a short date selection doesn't trail
    // off with a long run of empty bars.
    const last = data[data.length - 1];
    const endY = props.fullRange ? now.getFullYear() : last.year;
    const endM = props.fullRange ? now.getMonth() + 1 : last.month;

    while (y < endY || (y === endY && m <= endM)) {
        const key = `${y}-${m}`;
        result.push({ yearMonth: key, count: lookup.get(key) ?? 0 });
        m++;
        if (m > 12) { m = 1; y++; }
    }

    return result;
}

const barData = computed(() => buildCompleteSeries(rawData.value));
const isEmpty = computed(() => barData.value.every((b) => b.count === 0));

// --- D3 scales ---

const M = { top: 10, right: 20, bottom: 25, left: 40 };
const svgH = computed(() => props.height);
const innerH = computed(() => svgH.value - M.top - M.bottom);

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
    scaleLinear().domain([0, yMax.value]).range([innerH.value, 0]).nice()
);

// --- D3 axis directives ---

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

const vYaxis: ObjectDirective<SVGGElement> = { mounted: applyYAxis, updated: applyYAxis };
const vXaxis: ObjectDirective<SVGGElement> = { mounted: applyXAxis, updated: applyXAxis };

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

// --- Brush (fullRange mode only) ---
// The brush shows the currently selected date range as a highlighted region and
// lets users drag the left/right handles to adjust filtersStore.startDate/endDate.

const svgEl = ref<SVGSVGElement | null>(null);

type DragTarget = "left" | "right" | null;
const dragging = ref<DragTarget>(null);
const hovering = ref<DragTarget>(null);
const dragStartClientX = ref(0);
const dragStartBrushLeft = ref(0);
const dragStartBrushRight = ref(0);

// Convert a date string ("YYYY-MM-DD") to an x pixel within the inner chart group.
// When null: falls back to the chart's left (0) or right (innerW) edge.
function dateToInnerX(dateStr: string | null, edge: "left" | "right"): number {
    const domain = xScale.value.domain();
    if (domain.length === 0) return edge === "left" ? 0 : innerW.value;
    if (!dateStr) return edge === "left" ? 0 : innerW.value;

    const [y, m] = dateStr.split("-").map(Number);
    const key = `${y}-${m}`;
    const x = xScale.value(key);
    if (x !== undefined) {
        return edge === "left" ? x : x + xScale.value.bandwidth();
    }
    // Key outside domain: clamp to chart edges
    return edge === "left" ? 0 : innerW.value;
}

// Find the domain key whose band center is closest to a given inner-group x pixel.
function innerXToKey(x: number): string {
    const domain = xScale.value.domain();
    if (domain.length === 0) return "";
    let closest = domain[0];
    let closestDist = Infinity;
    for (const key of domain) {
        const bx = xScale.value(key)!;
        const center = bx + xScale.value.bandwidth() / 2;
        const dist = Math.abs(center - x);
        if (dist < closestDist) { closestDist = dist; closest = key; }
    }
    return closest;
}

// "YYYY-M" → "YYYY-MM-01" (first day of the month)
function keyToStartDate(key: string): string {
    const [y, m] = key.split("-").map(Number);
    return `${y}-${String(m).padStart(2, "0")}-01`;
}

// "YYYY-M" → "YYYY-MM-DD" (last day of the month)
function keyToEndDate(key: string): string {
    const [y, m] = key.split("-").map(Number);
    const lastDay = new Date(y, m, 0).getDate();
    return `${y}-${String(m).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
}

const brushLeft = computed(() => dateToInnerX(filtersStore.startDate, "left"));
const brushRight = computed(() => dateToInnerX(filtersStore.endDate, "right"));

// Human-readable label shown above the handle (YYYY-MM format)
const brushLeftLabel = computed(() =>
    filtersStore.startDate ? filtersStore.startDate.substring(0, 7) : null
);
const brushRightLabel = computed(() =>
    filtersStore.endDate ? filtersStore.endDate.substring(0, 7) : null
);

function getSvgInnerX(clientX: number): number {
    if (!svgEl.value) return 0;
    const rect = svgEl.value.getBoundingClientRect();
    return clientX - rect.left - M.left;
}

function onHandlePointerDown(event: PointerEvent, target: DragTarget) {
    event.preventDefault();
    dragging.value = target;
    dragStartClientX.value = event.clientX;
    dragStartBrushLeft.value = brushLeft.value;
    dragStartBrushRight.value = brushRight.value;

    const onMove = (e: PointerEvent) => {
        const x = getSvgInnerX(e.clientX);
        const step = xScale.value.step();
        if (dragging.value === "left") {
            const clamped = Math.max(0, Math.min(dragStartBrushRight.value - step, x));
            const key = innerXToKey(clamped);
            // Clear startDate if dragged all the way to the left edge
            filtersStore.startDate = clamped <= step / 2 ? null : keyToStartDate(key);
        } else if (dragging.value === "right") {
            const clamped = Math.max(dragStartBrushLeft.value + step, Math.min(innerW.value, x));
            const key = innerXToKey(clamped);
            // Clear endDate if dragged all the way to the right edge
            filtersStore.endDate = clamped >= innerW.value - step / 2 ? null : keyToEndDate(key);
        }
    };

    const onUp = () => {
        dragging.value = null;
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
}
</script>

<template>
    <div ref="wrapperEl" class="histogram-wrapper">
        <div v-if="!loading && isEmpty" class="histogram-empty">
            {{ t("message.noDataToShowInHistogram") }}
        </div>

        <svg
            v-else
            ref="svgEl"
            :width="containerWidth"
            :height="svgH"
            class="histogram-svg"
            :class="{ 'brush-mode': props.fullRange }"
            aria-hidden="true"
        >
            <g :transform="`translate(${M.left}, ${M.top})`">
                <!-- Data bars -->
                <rect
                    v-for="bar in barData"
                    :key="bar.yearMonth"
                    :x="xScale(bar.yearMonth)"
                    :y="yScale(bar.count)"
                    :width="xScale.bandwidth()"
                    :height="innerH - yScale(bar.count)"
                    class="histogram-bar"
                />

                <!-- Brush overlay (fullRange mode only) -->
                <template v-if="props.fullRange">
                    <!-- Dim zones outside the selection -->
                    <rect
                        v-if="brushLeft > 0"
                        :x="0" :y="0"
                        :width="brushLeft" :height="innerH"
                        class="brush-dim"
                    />
                    <rect
                        v-if="brushRight < innerW"
                        :x="brushRight" :y="0"
                        :width="innerW - brushRight" :height="innerH"
                        class="brush-dim"
                    />

                    <!-- Left handle -->
                    <line
                        :x1="brushLeft" :y1="0"
                        :x2="brushLeft" :y2="innerH"
                        class="brush-handle-line"
                        :class="{ active: dragging === 'left' || hovering === 'left' }"
                    />
                    <!-- Grip thumb (centered vertically) -->
                    <rect
                        :x="brushLeft - 6" :y="innerH / 2 - 14"
                        width="12" height="28" rx="3"
                        class="brush-grip"
                        :class="{ active: dragging === 'left' || hovering === 'left' }"
                    />
                    <line v-for="dy in [-5, 0, 5]" :key="dy"
                        :x1="brushLeft - 3" :y1="innerH / 2 + dy"
                        :x2="brushLeft + 3" :y2="innerH / 2 + dy"
                        class="brush-grip-dot"
                    />
                    <!-- Date label (shown when hovered, dragged, or date is set) -->
                    <text
                        v-if="brushLeftLabel || dragging === 'left' || hovering === 'left'"
                        :x="brushLeft"
                        :y="-3"
                        text-anchor="middle"
                        class="brush-label"
                    >{{ brushLeftLabel ?? "▶" }}</text>
                    <!-- Wide invisible hit area -->
                    <rect
                        :x="brushLeft - 8" :y="0"
                        width="16" :height="innerH"
                        class="brush-handle-hit"
                        @pointerdown="onHandlePointerDown($event, 'left')"
                        @pointerenter="hovering = 'left'"
                        @pointerleave="hovering = null"
                    />

                    <!-- Right handle -->
                    <line
                        :x1="brushRight" :y1="0"
                        :x2="brushRight" :y2="innerH"
                        class="brush-handle-line"
                        :class="{ active: dragging === 'right' || hovering === 'right' }"
                    />
                    <rect
                        :x="brushRight - 6" :y="innerH / 2 - 14"
                        width="12" height="28" rx="3"
                        class="brush-grip"
                        :class="{ active: dragging === 'right' || hovering === 'right' }"
                    />
                    <line v-for="dy in [-5, 0, 5]" :key="dy"
                        :x1="brushRight - 3" :y1="innerH / 2 + dy"
                        :x2="brushRight + 3" :y2="innerH / 2 + dy"
                        class="brush-grip-dot"
                    />
                    <text
                        v-if="brushRightLabel || dragging === 'right' || hovering === 'right'"
                        :x="brushRight"
                        :y="-3"
                        text-anchor="middle"
                        class="brush-label"
                    >{{ brushRightLabel ?? "◀" }}</text>
                    <rect
                        :x="brushRight - 8" :y="0"
                        width="16" :height="innerH"
                        class="brush-handle-hit"
                        @pointerdown="onHandlePointerDown($event, 'right')"
                        @pointerenter="hovering = 'right'"
                        @pointerleave="hovering = null"
                    />
                </template>

                <!-- Axes (rendered last so labels sit on top of brush overlay) -->
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

/* Brush styles */
.brush-dim {
    fill: #000;
    opacity: 0.35;
    pointer-events: none;
}

.brush-handle-line {
    stroke: var(--p-primary-400, #2dd4bf);
    stroke-width: 2;
    pointer-events: none;
    transition: stroke-width 0.1s;
}
.brush-handle-line.active {
    stroke-width: 3;
    stroke: #fff;
}

/* Grip thumb */
.brush-grip {
    fill: var(--p-primary-500, #00a58d);
    opacity: 0.85;
    pointer-events: none;
    transition: opacity 0.1s;
}
.brush-grip.active {
    opacity: 1;
    fill: #fff;
}

/* Three horizontal grip lines inside the thumb */
.brush-grip-dot {
    stroke: rgba(0, 0, 0, 0.45);
    stroke-width: 1.5;
    pointer-events: none;
}

/* Date label above the handle */
.brush-label {
    font-size: 9px;
    font-weight: 600;
    fill: var(--p-primary-300, #5eead4);
    pointer-events: none;
}

/* Wide invisible hit target for easy grab */
.brush-handle-hit {
    fill: transparent;
    cursor: ew-resize;
}

.brush-mode {
    cursor: default;
}
</style>
