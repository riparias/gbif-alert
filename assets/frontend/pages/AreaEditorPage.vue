<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, markRaw } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Select from "primevue/select";
import { Map as OLMap, View } from "ol";
import { fromLonLat } from "ol/proj";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import { GeoJSON } from "ol/format";
import { Draw, Modify, Select as OLSelect, Snap } from "ol/interaction";
import { Style, Stroke, Fill } from "ol/style";
import Feature from "ol/Feature";
import type { Polygon } from "ol/geom";
import { MultiPolygon as OLMultiPolygon } from "ol/geom";
import { useBaseLayer, makeBaseLayer, BASE_LAYER_OPTIONS } from "../composables/useBaseLayer";
import { getCsrf } from "../utils/csrf";
import "ol/ol.css";

type ActiveMode = "draw" | "edit" | "delete";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const toast = useToast();
const confirm = useConfirm();

const areaId = computed((): number | null => {
    const id = route.params.id;
    return id ? parseInt(id as string, 10) : null;
});
const isEditMode = computed(() => areaId.value !== null);

const areaName = ref("");
const polygonCount = ref(0);
const activeMode = ref<ActiveMode>("draw");
const isDirty = ref(false);
const saving = ref(false);
const loading = ref(false);
const errorMessage = ref<string | null>(null);
const pendingDeleteFeature = ref<Feature | null>(null);

const { selectedBaseLayerId, attachToMap } = useBaseLayer();
const mapEl = ref<HTMLElement | null>(null);
let olMap: OLMap | null = null;

const vectorSource = new VectorSource();
const vectorLayer = markRaw(
    new VectorLayer({
        source: vectorSource,
        style: new Style({
            stroke: new Stroke({ color: "#0b6efd", width: 3 }),
            fill: new Fill({ color: "rgba(11, 110, 253, 0.1)" }),
        }),
    })
);

let drawInteraction: Draw | null = null;
let modifyInteraction: Modify | null = null;
let selectInteraction: OLSelect | null = null;
let snapInteraction: Snap | null = null;

function clearInteractions(): void {
    if (!olMap) return;
    for (const i of [drawInteraction, modifyInteraction, selectInteraction, snapInteraction]) {
        if (i) olMap.removeInteraction(i);
    }
    drawInteraction = null;
    modifyInteraction = null;
    selectInteraction = null;
    snapInteraction = null;
}

function activateDrawMode(): void {
    clearInteractions();
    if (!olMap) return;
    drawInteraction = markRaw(new Draw({ source: vectorSource, type: "Polygon" }));
    drawInteraction.on("drawend", () => {
        polygonCount.value++;
        isDirty.value = true;
    });
    snapInteraction = markRaw(new Snap({ source: vectorSource }));
    olMap.addInteraction(drawInteraction);
    olMap.addInteraction(snapInteraction);
    activeMode.value = "draw";
    pendingDeleteFeature.value = null;
}

function activateEditMode(): void {
    clearInteractions();
    if (!olMap) return;
    modifyInteraction = markRaw(new Modify({ source: vectorSource }));
    modifyInteraction.on("modifyend", () => { isDirty.value = true; });
    snapInteraction = markRaw(new Snap({ source: vectorSource }));
    olMap.addInteraction(modifyInteraction);
    olMap.addInteraction(snapInteraction);
    activeMode.value = "edit";
    pendingDeleteFeature.value = null;
}

function activateDeleteMode(): void {
    clearInteractions();
    if (!olMap) return;
    selectInteraction = markRaw(new OLSelect());
    selectInteraction.on("select", (e) => {
        if (e.selected.length > 0) {
            pendingDeleteFeature.value = e.selected[0];
        }
    });
    olMap.addInteraction(selectInteraction);
    activeMode.value = "delete";
}

function confirmDeletePolygon(): void {
    if (!pendingDeleteFeature.value) return;
    vectorSource.removeFeature(pendingDeleteFeature.value);
    polygonCount.value--;
    isDirty.value = true;
    activateEditMode();
}

function cancelDeletePolygon(): void {
    selectInteraction?.getFeatures().clear();
    pendingDeleteFeature.value = null;
    activateEditMode();
}

const canSave = computed(
    () => areaName.value.trim() !== "" && polygonCount.value > 0 && !saving.value
);
const canDeletePolygon = computed(() => polygonCount.value > 1);

async function save(): Promise<void> {
    if (!canSave.value) return;
    saving.value = true;
    errorMessage.value = null;

    const geojson = new GeoJSON().writeFeaturesObject(
        vectorSource.getFeatures(),
        { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857" }
    );

    const url = isEditMode.value
        ? `/api/v2/areas/${areaId.value}/`
        : "/api/v2/areas/from-drawing/";
    const method = isEditMode.value ? "PATCH" : "POST";

    const resp = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
        body: JSON.stringify({ name: areaName.value, geojson }),
    });

    saving.value = false;

    if (resp.ok) {
        toast.add({ severity: "success", summary: t("message.areaSaved"), life: 3000 });
        await router.push("/my-custom-areas");
    } else {
        const data = await resp.json();
        errorMessage.value = data.detail ?? t("message.unexpectedError");
    }
}

function promptDeleteArea(): void {
    confirm.require({
        message: t("message.confirmDeleteArea"),
        header: t("message.confirmDeleteAreaHeader"),
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: doDeleteArea,
    });
}

async function doDeleteArea(): Promise<void> {
    const resp = await fetch(`/api/v2/areas/${areaId.value}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrf() },
    });
    if (resp.status === 204) {
        toast.add({ severity: "success", summary: t("message.areaDeleted"), life: 3000 });
        await router.push("/my-custom-areas");
    } else if (resp.status === 409) {
        const data = await resp.json();
        errorMessage.value = data.detail;
    }
}

onMounted(async () => {
    olMap = markRaw(
        new OLMap({
            target: mapEl.value!,
            layers: [markRaw(makeBaseLayer("osmHot")), vectorLayer],
            view: new View({ zoom: 2, center: fromLonLat([0, 20]) }),
        })
    );
    attachToMap(olMap);

    if (isEditMode.value && areaId.value !== null) {
        loading.value = true;
        const resp = await fetch(`/api/v2/areas/${areaId.value}/geojson/`);
        if (resp.ok) {
            const geojson = await resp.json();

            // The Django GeoJSON serializer includes model fields as properties.
            // Extract the area name from the first feature's properties.
            const name: string | undefined = geojson.features?.[0]?.properties?.name;
            if (name) areaName.value = name;

            // Split any MultiPolygon feature into individual Polygon features
            // so each polygon can be independently selected and deleted.
            const rawFeatures = new GeoJSON().readFeatures(geojson, {
                dataProjection: "EPSG:4326",
                featureProjection: "EPSG:3857",
            });
            const splitFeatures: Feature[] = [];
            for (const feat of rawFeatures) {
                const geom = feat.getGeometry();
                if (geom?.getType() === "MultiPolygon") {
                    const mp = geom as OLMultiPolygon;
                    for (const poly of mp.getPolygons()) {
                        splitFeatures.push(new Feature<Polygon>({ geometry: poly }));
                    }
                } else {
                    splitFeatures.push(feat);
                }
            }
            vectorSource.addFeatures(splitFeatures);
            polygonCount.value = splitFeatures.length;

            const extent = vectorSource.getExtent();
            if (extent && extent.every(isFinite)) {
                olMap.getView().fit(extent, { padding: [20, 20, 20, 20] });
            }
        }
        loading.value = false;
        activateEditMode();
    } else {
        activateDrawMode();
    }
});

onUnmounted(() => {
    olMap?.setTarget(undefined);
    olMap = null;
});
</script>

<template>
    <div class="editor-page">
        <!-- Map area -->
        <div ref="mapEl" class="editor-map">
            <!-- Base layer control - floating top-right, same style as BaseMap.vue -->
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
            </div>
            <!-- Hint overlay shown in create mode before any polygon is drawn -->
            <div v-if="!isEditMode && polygonCount === 0 && !loading" class="draw-hint">
                {{ t("message.clickToStartDrawing") }}
            </div>
        </div>

        <!-- Right sidebar -->
        <div class="editor-sidebar">
            <!-- Area name input -->
            <div class="sidebar-section">
                <label class="sidebar-label" for="editor-area-name">
                    {{ t("message.areaName") }}
                </label>
                <InputText
                    id="editor-area-name"
                    v-model="areaName"
                    class="w-full"
                    :placeholder="t('message.areaName') + '...'"
                />
            </div>

            <div class="sidebar-divider" />

            <!-- Tool buttons -->
            <div class="sidebar-section">
                <div class="sidebar-label">{{ t("message.drawingTool") }}</div>

                <!-- Normal tool list -->
                <div v-if="!(activeMode === 'delete' && pendingDeleteFeature)" class="tool-buttons">
                    <Button
                        :label="t('message.drawPolygon')"
                        icon="pi pi-pencil"
                        :outlined="activeMode !== 'draw'"
                        size="small"
                        fluid
                        @click="activateDrawMode"
                    />
                    <Button
                        :label="t('message.editVertices')"
                        icon="pi pi-arrows-alt"
                        :outlined="activeMode !== 'edit'"
                        size="small"
                        fluid
                        @click="activateEditMode"
                    />
                    <Button
                        :label="t('message.deletePolygon')"
                        icon="pi pi-trash"
                        :outlined="activeMode !== 'delete'"
                        :disabled="!canDeletePolygon"
                        size="small"
                        fluid
                        @click="activateDeleteMode"
                    />
                </div>

                <!-- Delete polygon confirmation (replaces tool list) -->
                <div v-else class="delete-confirm">
                    <p class="delete-confirm-label">{{ t("message.confirmDeletePolygon") }}</p>
                    <Button
                        :label="t('message.yesImSure')"
                        severity="danger"
                        size="small"
                        fluid
                        @click="confirmDeletePolygon"
                    />
                    <Button
                        :label="t('message.cancel')"
                        severity="secondary"
                        size="small"
                        fluid
                        @click="cancelDeletePolygon"
                    />
                </div>

                <small class="sidebar-hint">
                    {{ t("message.polygonCount", { count: polygonCount }) }}
                </small>
            </div>

            <!-- Spacer pushes save/delete to bottom -->
            <div class="sidebar-spacer" />

            <!-- Unsaved changes indicator (edit mode only) -->
            <div v-if="isEditMode && isDirty" class="unsaved-indicator">
                {{ t("message.unsavedChanges") }}
            </div>

            <!-- API error message -->
            <Message v-if="errorMessage" severity="error" class="mb-2" :closable="false">
                {{ errorMessage }}
            </Message>

            <!-- Save / Cancel -->
            <div class="sidebar-section">
                <Button
                    :label="t('message.save')"
                    :disabled="!canSave"
                    :loading="saving"
                    fluid
                    @click="save"
                />
                <Button
                    :label="t('message.cancel')"
                    severity="secondary"
                    class="mt-2"
                    fluid
                    @click="router.push('/my-custom-areas')"
                />
            </div>

            <!-- Delete area button (edit mode only) -->
            <template v-if="isEditMode">
                <div class="sidebar-divider" />
                <div class="sidebar-section">
                    <Button
                        :label="t('message.deleteAreaButton')"
                        icon="pi pi-trash"
                        severity="danger"
                        outlined
                        fluid
                        @click="promptDeleteArea"
                    />
                </div>
            </template>
        </div>
    </div>
</template>

<style scoped>
.editor-page {
    display: flex;
    /* Subtract the app header height. */
    height: calc(100vh - 60px);
    overflow: hidden;
}

.editor-map {
    flex: 1;
    position: relative;
}

/* Replicates the floating controls style from BaseMap.vue */
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

.draw-hint {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(4px);
    border-radius: 8px;
    padding: 0.75rem 1.25rem;
    font-size: 0.95rem;
    color: var(--p-text-color);
    pointer-events: none;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.editor-sidebar {
    width: 220px;
    flex-shrink: 0;
    background: var(--p-surface-card);
    border-left: 1px solid var(--p-surface-border);
    display: flex;
    flex-direction: column;
    padding: 1rem 0.875rem;
    overflow-y: auto;
}

.sidebar-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}

.sidebar-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--p-text-muted-color);
    font-weight: 600;
}

.sidebar-hint {
    font-size: 0.75rem;
    color: var(--p-text-muted-color);
}

.sidebar-divider {
    border-top: 1px solid var(--p-surface-border);
    margin: 0.5rem 0;
}

.sidebar-spacer {
    flex: 1;
}

.tool-buttons {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.unsaved-indicator {
    font-size: 0.8rem;
    color: var(--p-orange-400);
    margin-bottom: 0.5rem;
}

.delete-confirm {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.delete-confirm-label {
    margin: 0;
    font-size: 0.875rem;
}
</style>
