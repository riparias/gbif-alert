<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, markRaw } from "vue";
import { useI18n } from "vue-i18n";
import { Map as OLMap, View } from "ol";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import StadiaMaps from "ol/source/StadiaMaps";
import OSM from "ol/source/OSM";
import XYZ from "ol/source/XYZ";
import Select from "primevue/select";
import "ol/ol.css";

const props = withDefaults(
    defineProps<{
        height?: string;
        initialLon?: number;
        initialLat?: number;
        initialZoom?: number;
    }>(),
    {
        height: "480px",
        initialLon: 0,
        initialLat: 20,
        initialZoom: 2,
    }
);

const { t } = useI18n();

const BASE_LAYER_OPTIONS = [
    { id: "osmHot", label: "OSM HOT" },
    { id: "toner", label: "Stamen Toner" },
    { id: "esriImagery", label: "ESRI World Imagery" },
] as const;

const selectedBaseLayerId = ref<string>("osmHot");
const mapEl = ref<HTMLElement | null>(null);
let olMap: OLMap | null = null;

function makeBaseLayer(id: string): TileLayer<any> {
    if (id === "toner") {
        return new TileLayer({ source: new StadiaMaps({ layer: "stamen_toner" }) });
    }
    if (id === "esriImagery") {
        return new TileLayer({
            source: new XYZ({
                url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                maxZoom: 19,
            }),
        });
    }
    return new TileLayer({
        source: new OSM({ url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png" }),
    });
}

watch(selectedBaseLayerId, (newId) => {
    if (!olMap) return;
    const layers = olMap.getLayers();
    layers.removeAt(0);
    layers.insertAt(0, markRaw(makeBaseLayer(newId)));
});

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
        <div class="map-float-controls">
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
