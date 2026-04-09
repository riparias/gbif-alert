<script setup lang="ts">
import { ref, onMounted, markRaw } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Card from "primevue/card";
import Tag from "primevue/tag";
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
    <Card class="area-card">
        <template #title>
            <span class="area-name">{{ area.name }}</span>
        </template>

        <template #content>
            <BaseMap ref="baseMapRef" height="200px" :show-controls="false" />
            <div v-if="area.tags.length > 0" class="tags-row">
                <Tag
                    v-for="tag in area.tags"
                    :key="tag"
                    :value="tag"
                    severity="secondary"
                    class="area-tag"
                />
            </div>
        </template>

        <template #footer>
            <div class="card-actions">
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
                    outlined
                    @click="confirmDelete"
                />
            </div>
        </template>
    </Card>
</template>

<style scoped>
.area-card {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.area-name {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--p-primary-color);
}

.tags-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.6rem;
}

.area-tag {
    font-size: 0.75rem;
}

:deep(.p-card-footer) {
    border-top: 1px solid var(--p-content-border-color);
    padding-top: 0.75rem;
    margin-top: 0.25rem;
}

.card-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
</style>
