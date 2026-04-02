<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import ProgressSpinner from "primevue/progressspinner";
import ConfirmDialog from "primevue/confirmdialog";
import Toast from "primevue/toast";
import AreaCard from "../components/AreaCard.vue";
import AreaUploadDialog from "../components/AreaUploadDialog.vue";

const { t } = useI18n();

interface AreaOut {
    id: number;
    name: string;
    isUserSpecific: boolean;
    tags: string[];
}

const areas = ref<AreaOut[]>([]);
const loading = ref(true);
const showUploadDialog = ref(false);

async function loadAreas() {
    loading.value = true;
    const resp = await fetch("/api/v2/areas/");
    const data: AreaOut[] = await resp.json();
    areas.value = data.filter((a) => a.isUserSpecific);
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
                    <span>{{ area.name }}</span>
                    <AreaCard :area="area" @deleted="onAreaDeleted" />
                </div>
            </div>
        </template>

        <AreaUploadDialog
            v-model:visible="showUploadDialog"
            @created="onAreaCreated"
        />

        <ConfirmDialog />
        <Toast />
    </div>
</template>
