<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import ProgressSpinner from "primevue/progressspinner";

interface DataImport {
    id: number;
    name: string;
    startTimestamp: string;
}

const { t } = useI18n();
const imports = ref<DataImport[]>([]);
const loading = ref(true);

onMounted(async () => {
    const resp = await fetch("/api/v2/data-imports/");
    if (resp.ok) {
        imports.value = await resp.json();
    }
    loading.value = false;
});

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString();
}
</script>

<template>
    <div style="max-width: 800px; margin: 2rem auto; padding: 0 1rem;">
        <h1 style="margin-bottom: 1.5rem;">{{ t("message.aboutData") }}</h1>
        <ProgressSpinner v-if="loading" />
        <template v-else>
            <p v-if="imports.length === 0">{{ t("message.noDataImports") }}</p>
            <ul v-else style="list-style: none; padding: 0; display: flex; flex-direction: column; gap: 0.5rem;">
                <li
                    v-for="imp in imports"
                    :key="imp.id"
                    style="padding: 0.75rem 1rem; border: 1px solid var(--p-surface-200); border-radius: 6px;"
                >
                    <strong>{{ imp.name }}</strong> - {{ formatDate(imp.startTimestamp) }}
                </li>
            </ul>
        </template>
    </div>
</template>
