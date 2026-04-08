<script setup lang="ts">
import { ref, onMounted, markRaw } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import { getCsrf } from "../utils/csrf";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import { GeoJSON } from "ol/format";
import { Style, Stroke } from "ol/style";
import BaseMap from "./BaseMap.vue";
import type { components } from "../types/api";

type AreaOut = components["schemas"]["AreaOut"];

const props = defineProps<{ area: AreaOut }>();
const emit = defineEmits<{ deleted: [areaId: number] }>();

const { t } = useI18n();
const router = useRouter();
const confirm = useConfirm();
const toast = useToast();

const baseMapRef = ref<InstanceType<typeof BaseMap> | null>(null);

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

onMounted(async () => {
    const map = baseMapRef.value!.getOlMap()!;

    const resp = await fetch(`/api/v2/areas/${props.area.id}/geojson/`);
    const geojson = await resp.json();

    const vectorSource = new VectorSource({
        features: new GeoJSON().readFeatures(geojson, {
            dataProjection: "EPSG:4326",
            featureProjection: "EPSG:3857",
        }),
    });

    map.addLayer(
        markRaw(
            new VectorLayer({
                source: vectorSource,
                style: new Style({
                    stroke: new Stroke({ color: "#0b6efd", width: 3 }),
                }),
            })
        )
    );

    const extent = vectorSource.getExtent();
    if (extent && extent.every(isFinite)) {
        map.getView().fit(extent, { padding: [20, 20, 20, 20] });
    }
});
</script>

<template>
    <div class="area-card p-3 border-1 surface-border border-round mb-3">
        <h3 class="text-lg font-semibold mt-0 mb-2">{{ area.name }}</h3>
        <BaseMap ref="baseMapRef" height="200px" />
        <div class="flex gap-2 mt-2">
            <Button
                :label="t('message.editArea')"
                icon="pi pi-pencil"
                severity="secondary"
                size="small"
                @click="router.push(`/my-custom-areas/${props.area.id}/edit`)"
            />
            <Button
                :label="t('message.deleteArea')"
                icon="pi pi-trash"
                severity="danger"
                size="small"
                @click="confirmDelete"
            />
        </div>
    </div>
</template>
