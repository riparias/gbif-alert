<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import { getCsrf } from "../utils/csrf";
import { Map as OLMap, View } from "ol";
import TileLayer from "ol/layer/Tile";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import OSM from "ol/source/OSM";
import { GeoJSON } from "ol/format";
import { Style, Stroke } from "ol/style";
import "ol/ol.css";
import type { components } from "../types/api";

type AreaOut = components["schemas"]["AreaOut"];

const props = defineProps<{ area: AreaOut }>();
const emit = defineEmits<{ deleted: [areaId: number] }>();

const { t } = useI18n();
const confirm = useConfirm();
const toast = useToast();

const mapEl = ref<HTMLElement | null>(null);
let olMap: OLMap | null = null;

async function loadMap() {
    if (!mapEl.value) return;

    const resp = await fetch(`/api/v2/areas/${props.area.id}/geojson/`);
    const geojson = await resp.json();

    const vectorSource = new VectorSource({
        features: new GeoJSON().readFeatures(geojson, {
            dataProjection: "EPSG:4326",
            featureProjection: "EPSG:3857",
        }),
    });

    const vectorLayer = new VectorLayer({
        source: vectorSource,
        style: new Style({
            stroke: new Stroke({ color: "#0b6efd", width: 3 }),
        }),
    });

    olMap = new OLMap({
        target: mapEl.value,
        layers: [
            new TileLayer({
                source: new OSM({
                    url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
                }),
            }),
            vectorLayer,
        ],
        view: new View({ center: [0, 0], zoom: 2 }),
    });

    const extent = vectorSource.getExtent();
    if (extent && extent.every(isFinite)) {
        olMap.getView().fit(extent, { padding: [20, 20, 20, 20] });
    }
}

function confirmDelete() {
    confirm.require({
        message: t("message.confirmDeleteArea"),
        header: t("message.confirmDeleteAreaHeader"),
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: deleteArea,
    });
}

async function deleteArea() {
    const resp = await fetch(`/api/v2/areas/${props.area.id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrf() },
    });
    if (resp.status === 204) {
        toast.add({
            severity: "success",
            summary: t("message.areaDeleted"),
            life: 3000,
        });
        emit("deleted", props.area.id);
    } else if (resp.status === 409) {
        const data = await resp.json();
        toast.add({
            severity: "error",
            summary: t("message.cannotDeleteArea"),
            detail: data.detail,
            life: 6000,
        });
    }
}

onMounted(loadMap);
onUnmounted(() => {
    olMap?.setTarget(undefined);
    olMap = null;
});
</script>

<template>
    <div class="area-card p-3 border-1 surface-border border-round mb-3">
        <h3 class="text-lg font-semibold mt-0 mb-2">{{ area.name }}</h3>
        <div ref="mapEl" style="width: 100%; height: 200px;" class="mb-2"></div>
        <Button
            :label="t('message.deleteArea')"
            icon="pi pi-trash"
            severity="danger"
            size="small"
            @click="confirmDelete"
        />
    </div>
</template>
