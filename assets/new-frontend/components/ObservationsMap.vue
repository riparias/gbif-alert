<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, markRaw } from "vue";
import { debounce } from "lodash";
import { useI18n } from "vue-i18n";
import { Collection, Map as OLMap, Overlay } from "ol";
import VectorTileLayer from "ol/layer/VectorTile";
import VectorLayer from "ol/layer/Vector";
import LayerGroup from "ol/layer/Group";
import VectorTileSource from "ol/source/VectorTile";
import VectorSource from "ol/source/Vector";
import { MVT, GeoJSON } from "ol/format";
import { Style, Fill, Stroke, Circle as OLCircle, Text } from "ol/style";
import { scaleSequentialLog } from "d3-scale";
import { interpolateReds } from "d3-scale-chromatic";
import { hsl } from "d3-color";
import Slider from "primevue/slider";
import { useRouter, useRoute } from "vue-router";
import { useFiltersStore } from "../stores/filters";
import BaseMap from "./BaseMap.vue";

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const store = useFiltersStore();

// --- Map config injected by Django (via nav_config_json template tag) ---

interface MapConfig {
    initialPosition: { initialZoom: number; initialLat: number; initialLon: number };
    zoomLevelMinMaxQuery: number;
    tileServerUrlTemplate: string;
    tileServerAggregatedUrlTemplate: string;
    areasUrlTemplate: string;
    minMaxOccPerHexagonUrl: string;
    observationDetailsUrlTemplate: string;
}

const mapCfg: MapConfig = JSON.parse(
    document.getElementById("gbif-alert-nav-config")!.textContent!
).map;

// --- Controls ---

const opacity = ref<number>(0.8);

// --- DOM / component refs ---

const baseMapRef = ref<InstanceType<typeof BaseMap> | null>(null);
const popupEl = ref<HTMLElement | null>(null);

// --- OL objects (kept outside Vue reactivity) ---

let olMap: OLMap | null = null;
let aggregatedLayer: VectorTileLayer | null = null;
let simpleLayer: VectorTileLayer | null = null;
let popupOverlay: Overlay | null = null;
const areasCollection = markRaw(new Collection<VectorLayer<any>>());

// --- Hex color scale state ---

const hexMin = ref<number>(1);
const hexMax = ref<number>(1);

// --- Popup content (visibility is managed by OL via overlay.setPosition) ---

const popupObservations = ref<
    Array<{ gbifId: string; scientificName: string; vernacularName: string; stableId: string }>
>([]);

// Zoom level at which layers switch from aggregated hexagons to individual points
const LAYER_SWITCH_ZOOM = 13;

// --- Helpers ---

// Build filter query string in the bracket format expected by the legacy internal-api endpoints:
// ?speciesIds[]=1&speciesIds[]=2 (instead of the new API v2 format ?speciesIds=1&speciesIds=2)
function buildLegacyParams(): string {
    const p = new URLSearchParams();
    for (const id of store.speciesIds) p.append("speciesIds[]", String(id));
    for (const id of store.datasetsIds) p.append("datasetsIds[]", String(id));
    for (const id of store.areaIds) p.append("areaIds[]", String(id));
    for (const id of store.basisOfRecordIds) p.append("basisOfRecordIds[]", String(id));
    for (const id of store.initialDataImportIds) p.append("initialDataImportIds[]", String(id));
    if (store.startDate) p.set("startDate", store.startDate);
    if (store.endDate) p.set("endDate", store.endDate);
    if (store.status) p.set("status", store.status);
    p.set("verifiedFilter", store.verifiedFilter);
    p.set("areaFilterMode", store.areaFilterMode);
    if (store.approachingDistanceKm !== null)
        p.set("approachingDistanceKm", String(store.approachingDistanceKm));
    return p.toString();
}

function legibleTextColor(fillColor: string): string {
    return hsl(fillColor).l > 0.5 ? "#000" : "#fff";
}

// Returns a style function that uses the current hexMin/hexMax to compute fill colors.
// Must be called fresh each time hexMin or hexMax changes.
function makeAggregatedStyleFn() {
    const scale = scaleSequentialLog(interpolateReds).domain([
        Math.max(hexMin.value, 1),
        Math.max(hexMax.value, 1),
    ]);
    return function (feature: any): Style {
        const count = feature.getProperties()["count"] as number;
        const fillColor = scale(count);
        return new Style({
            stroke: new Stroke({ color: "grey", width: 1 }),
            fill: new Fill({ color: fillColor }),
            text: new Text({
                text: count.toString(),
                fill: new Fill({ color: legibleTextColor(fillColor) }),
            }),
        });
    };
}

function createAggregatedLayer(): VectorTileLayer {
    const qs = buildLegacyParams();
    return new VectorTileLayer({
        source: new VectorTileSource({
            format: new MVT(),
            url: mapCfg.tileServerAggregatedUrlTemplate + (qs ? `?${qs}` : ""),
        }),
        style: makeAggregatedStyleFn(),
        opacity: opacity.value,
        maxZoom: LAYER_SWITCH_ZOOM,
    });
}

function createSimpleLayer(): VectorTileLayer {
    const qs = buildLegacyParams();
    return new VectorTileLayer({
        source: new VectorTileSource({
            format: new MVT(),
            url: mapCfg.tileServerUrlTemplate + (qs ? `?${qs}` : ""),
        }),
        style: new Style({
            image: new OLCircle({ radius: 7, fill: new Fill({ color: "red" }) }),
        }),
        opacity: opacity.value,
        minZoom: LAYER_SWITCH_ZOOM,
    });
}

async function loadHexMinMax(): Promise<void> {
    const p = new URLSearchParams(buildLegacyParams());
    p.set("zoom", String(mapCfg.zoomLevelMinMaxQuery));
    try {
        const resp = await fetch(`${mapCfg.minMaxOccPerHexagonUrl}?${p}`);
        if (resp.ok) {
            const data = await resp.json();
            hexMin.value = data.min ?? 1;
            hexMax.value = data.max ?? 1;
        }
    } catch {
        // Non-fatal: keep current scale values
    }
}

async function refreshAreaOverlays(areaIds: number[]): Promise<void> {
    areasCollection.clear();
    for (const id of areaIds) {
        try {
            const resp = await fetch(mapCfg.areasUrlTemplate.replace("{id}", String(id)));
            if (!resp.ok) continue;
            const geojson = await resp.json();
            const source = new VectorSource({
                features: new GeoJSON().readFeatures(geojson, {
                    dataProjection: "EPSG:4326",
                    featureProjection: "EPSG:3857",
                }),
            });
            areasCollection.push(
                new VectorLayer({
                    source,
                    style: new Style({ stroke: new Stroke({ color: "#0b6efd", width: 3 }) }),
                })
            );
        } catch {
            // Skip areas that fail to load
        }
    }
}

function replaceDataLayers(): void {
    if (!olMap) return;
    if (aggregatedLayer) olMap.removeLayer(aggregatedLayer);
    if (simpleLayer) olMap.removeLayer(simpleLayer);
    void loadHexMinMax();
    aggregatedLayer = markRaw(createAggregatedLayer());
    simpleLayer = markRaw(createSimpleLayer());
    olMap.addLayer(aggregatedLayer);
    olMap.addLayer(simpleLayer);
}

const debouncedRefresh = debounce(() => {
    replaceDataLayers();
    void refreshAreaOverlays(store.areaIds);
}, 300);

function openObservationFromMap(stableId: string) {
    popupOverlay!.setPosition(undefined); // close the popup
    router.replace({ query: { ...route.query, obs: stableId } });
}

// --- Watchers ---

// Refresh color scale when min/max arrives after an async load
watch([hexMin, hexMax], () => {
    aggregatedLayer?.setStyle(makeAggregatedStyleFn());
});

// Propagate opacity changes to both data layers
watch(opacity, (val) => {
    aggregatedLayer?.setOpacity(val);
    simpleLayer?.setOpacity(val);
});

// Replace data layers (and area overlays) when any filter changes
watch(store, debouncedRefresh, { deep: true });

// --- Lifecycle ---

onMounted(() => {
    olMap = baseMapRef.value!.getOlMap()!;

    // Area overlays sit above tiles but below data layers
    olMap.addLayer(
        new LayerGroup({
            layers: areasCollection as unknown as Collection<any>,
            zIndex: 1000,
        })
    );

    // stopEvent: true so that clicks on the popup don't propagate to the map
    popupOverlay = markRaw(new Overlay({ element: popupEl.value!, stopEvent: true }));
    olMap.addOverlay(popupOverlay);

    replaceDataLayers();
    void refreshAreaOverlays(store.areaIds);

    olMap.on("click", (evt) => {
        const zoom = olMap!.getView().getZoom() ?? 0;
        if (zoom < LAYER_SWITCH_ZOOM) {
            popupOverlay!.setPosition(undefined);
            return;
        }

        const features = olMap!.getFeaturesAtPixel(evt.pixel);
        if (features.length === 0) {
            popupOverlay!.setPosition(undefined);
            return;
        }

        popupObservations.value = features.map((f) => {
            const props = f.getProperties();
            return {
                gbifId: String(props["gbif_id"]),
                scientificName: props["scientific_name"] as string,
                vernacularName: (props["vernacular_name"] as string) || "",
                stableId: props["stable_id"] as string,
            };
        });
        popupOverlay!.setPosition(evt.coordinate);
    });
});

onUnmounted(() => {
    debouncedRefresh.cancel();
    // BaseMap handles olMap.setTarget(undefined) in its own onUnmounted
});
</script>

<template>
    <BaseMap
        ref="baseMapRef"
        height="480px"
        :initial-lon="mapCfg.initialPosition.initialLon"
        :initial-lat="mapCfg.initialPosition.initialLat"
        :initial-zoom="mapCfg.initialPosition.initialZoom"
    >
        <!-- Opacity slider added to the floating controls panel -->
        <template #extra-controls>
            <div class="opacity-row">
                <span class="opacity-label">{{ t("message.dataLayerOpacity") }}</span>
                <Slider
                    v-model="opacity"
                    :min="0"
                    :max="1"
                    :step="0.1"
                    class="opacity-slider"
                />
            </div>
        </template>

        <!-- Observation popup (OL Overlay positions this at the click coordinate) -->
        <div ref="popupEl" class="map-popup">
            <button class="popup-close" @click="popupOverlay?.setPosition(undefined)">
                &#x2715;
            </button>
            <ul class="popup-list">
                <li v-for="obs in popupObservations" :key="obs.gbifId">
                    <a
                        href="#"
                        @click.prevent="openObservationFromMap(obs.stableId)"
                    ><em>{{ obs.scientificName }}</em><span v-if="obs.vernacularName"> ({{ obs.vernacularName }})</span></a>
                    <span class="popup-gbif-id"> - {{ obs.gbifId }}</span>
                </li>
            </ul>
        </div>
    </BaseMap>
</template>

<style scoped>
/* Opacity control injected into the BaseMap floating controls panel via slot */
.opacity-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.opacity-label {
    font-size: 0.78rem;
    white-space: nowrap;
    color: var(--p-text-color);
    flex-shrink: 0;
}

.opacity-slider {
    width: 80px;
}

/* OL renders the popup inside .ol-overlays-container, which uses absolute positioning.
   The popup is hidden when OL sets position to undefined (display: none via OL internals).
   We just style its appearance here. */
.map-popup {
    background: var(--p-surface-0, #fff);
    border: 1px solid var(--p-surface-300, #ccc);
    border-radius: 4px;
    padding: 0.4rem 0.6rem;
    min-width: 160px;
    max-width: 280px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
}

.popup-close {
    float: right;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    padding: 0 0.2rem;
    line-height: 1.4;
}

.popup-list {
    list-style: none;
    margin: 0.2rem 0 0;
    padding: 0;
}

.popup-list li {
    padding: 0.2rem 0;
    font-size: 0.85rem;
}

.popup-gbif-id {
    color: var(--p-text-muted-color);
    font-size: 0.8rem;
}
</style>
