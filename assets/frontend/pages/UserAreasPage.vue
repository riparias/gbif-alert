<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import Button from "primevue/button";
import Menu from "primevue/menu";
import ProgressSpinner from "primevue/progressspinner";
import AreaCard from "../components/AreaCard.vue";
import AreaUploadDialog from "../components/AreaUploadDialog.vue";
import type { components } from "../types/api";

type AreaOut = components["schemas"]["AreaOut"];

const { t } = useI18n();
const router = useRouter();

const addAreaMenu = ref();
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

const addAreaItems = computed(() => [
    {
        label: t("message.drawOnMap"),
        icon: "pi pi-pencil",
        command: () => router.push("/my-custom-areas/new"),
    },
    {
        label: t("message.uploadFile"),
        icon: "pi pi-upload",
        command: () => {
            showUploadDialog.value = true;
        },
    },
]);

onMounted(loadAreas);
</script>

<template>
    <div class="page-content user-areas-page">
        <div class="page-header">
            <h1>{{ t("message.navMyCustomAreas") }}</h1>
            <Button
                :label="t('message.addArea')"
                icon="pi pi-plus"
                aria-haspopup="true"
                @click="addAreaMenu.toggle($event)"
            />
            <Menu ref="addAreaMenu" :model="addAreaItems" popup />
        </div>

        <ProgressSpinner v-if="loading" />

        <template v-else>
            <p v-if="areas.length === 0" class="text-color-secondary">
                {{ t("message.noCustomAreasYet") }}
            </p>

            <div v-else class="areas-grid">
                <AreaCard
                    v-for="area in areas"
                    :key="area.id"
                    :area="area"
                    @deleted="onAreaDeleted"
                />
            </div>
        </template>

        <AreaUploadDialog
            v-model:visible="showUploadDialog"
            @created="onAreaCreated"
        />
    </div>
</template>

<style scoped>
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.page-header h1 {
    margin: 0;
}

.areas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 1.25rem;
    align-items: start;
}

.text-color-secondary {
    color: var(--p-text-muted-color);
}
</style>
