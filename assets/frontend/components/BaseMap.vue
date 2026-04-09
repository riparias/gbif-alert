<script setup lang="ts">
import { ref, onMounted, onUnmounted, markRaw } from "vue";
import { useI18n } from "vue-i18n";
import { Map as OLMap, View } from "ol";
import { fromLonLat } from "ol/proj";
import Select from "primevue/select";
import "ol/ol.css";
import { useBaseLayer, makeBaseLayer, BASE_LAYER_OPTIONS } from "../composables/useBaseLayer";

const props = withDefaults(
    defineProps<{
        height?: string;
        initialLon?: number;
        initialLat?: number;
        initialZoom?: number;
        showControls?: boolean;
    }>(),
    {
        height: "480px",
        initialLon: 0,
        initialLat: 20,
        initialZoom: 2,
        showControls: true,
    }
);

const { t } = useI18n();
const { selectedBaseLayerId, attachToMap } = useBaseLayer();
const mapEl = ref<HTMLElement | null>(null);
let olMap: OLMap | null = null;

onMounted(() => {
    olMap = markRaw(
        new OLMap({
            target: mapEl.value!,
            layers: [markRaw(makeBaseLayer("osmHot"))],
            view: new View({
                zoom: props.initialZoom,
                center: fromLonLat([props.initialLon, props.initialLat]),
            }),
        })
    );
    attachToMap(olMap);
});

onUnmounted(() => {
    olMap?.setTarget(undefined);
    olMap = null;
});

defineExpose({ getOlMap: () => olMap });
</script>

<template>
    <div class="base-map-wrapper" :style="{ height: props.height }">
        <!-- Floating controls panel, top-right corner -->
        <div v-if="props.showControls" class="map-float-controls">
            <div class="float-control-row">
                <span class="float-control-label">{{ t("message.baseLayer") }}</span>
                <Select
                    v-model="selectedBaseLayerId"
                    :options="BASE_LAYER_OPTIONS"
                    option-label="label"
                    option-value="id"
                    size="small"
                    class="base-layer-select"
                />
            </div>
            <!-- Extra controls injected by the consumer (e.g. opacity slider) -->
            <slot name="extra-controls" />
        </div>

        <!-- OL map target -->
        <div ref="mapEl" class="map-canvas" />

        <!-- Slot for overlay/popup elements that OL Overlays reference -->
        <slot />
    </div>
</template>

<style scoped>
.base-map-wrapper {
    position: relative;
    width: 100%;
}

.map-canvas {
    width: 100%;
    height: 100%;
}

.map-float-controls {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    z-index: 100;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(3px);
    border-radius: 6px;
    padding: 0.5rem 0.65rem;
    box-shadow: 0 1px 5px rgba(0, 0, 0, 0.22);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 155px;
    pointer-events: auto;
}

.float-control-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.float-control-label {
    font-size: 0.78rem;
    white-space: nowrap;
    color: var(--p-text-color);
    flex-shrink: 0;
}

.base-layer-select {
    flex: 1;
    min-width: 0;
}
</style>
