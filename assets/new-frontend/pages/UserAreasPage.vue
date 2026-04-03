<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import ProgressSpinner from "primevue/progressspinner";
import AreaCard from "../components/AreaCard.vue";
import AreaUploadDialog from "../components/AreaUploadDialog.vue";
import type { components } from "../types/api";

type AreaOut = components["schemas"]["AreaOut"];

const { t } = useI18n();

const areas = ref<AreaOut[]>([]);
const loading = ref(true);
const showUploadDialog = ref(false);

async function loadAreas() {
    loading.value = true;
    const resp = await fetch("/api/v2/areas/");
    if (resp.ok) {
        const data: AreaOut[] = await resp.json();
        areas.value = data.filter((a) => a.isUserSpecific);
    }
    loading.value = false;
}

function onAreaCreated(area: AreaOut) {
    areas.value.push(area);
    showUploadDialog.value = false;
}

function onAreaDeleted(areaId: number) {
    areas.value = areas.value.filter((a) => a.id !== areaId);
}

onMounted(loadAreas);
</script>

<template>
    <div class="p-4">
        <div class="flex align-items-center justify-content-between mb-4">
            <h1 class="text-2xl font-bold m-0">{{ t("message.navMyCustomAreas") }}</h1>
            <Button
                :label="t('message.newArea')"
                icon="pi pi-plus"
                @click="showUploadDialog = true"
            />
        </div>

        <ProgressSpinner v-if="loading" />

        <template v-else>
            <p v-if="areas.length === 0" class="text-color-secondary">
                {{ t("message.noCustomAreasYet") }}
            </p>

            <div v-else class="grid">
                <div v-for="area in areas" :key="area.id" class="col-12 md:col-6 lg:col-4">
                    <AreaCard :area="area" @deleted="onAreaDeleted" />
                </div>
            </div>
        </template>

        <AreaUploadDialog
            v-model:visible="showUploadDialog"
            @created="onAreaCreated"
        />
    </div>
</template>
