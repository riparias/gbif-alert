<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import ProgressSpinner from "primevue/progressspinner";

interface DataImport {
    id: number;
    name: string;
    startTimestamp: string;
    endTimestamp: string | null;
    importedCount: number;
    newObservationsCount: number;
    skippedCount: number;
    gbifDownloadId: string;
}

const { t, locale } = useI18n();
const imports = ref<DataImport[]>([]);
const loading = ref(true);
const showAll = ref(false);

onMounted(async () => {
    const resp = await fetch("/api/v2/data-imports/");
    if (resp.ok) {
        imports.value = await resp.json();
    }
    loading.value = false;
});

function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString(locale.value);
}

function gbifDownloadUrl(downloadId: string): string {
    return `https://www.gbif.org/occurrence/download/${downloadId}`;
}
</script>

<template>
    <div class="page-content--wide">
        <h1 style="margin-bottom: 1rem;">{{ t("message.aboutData") }}</h1>

        <p>
            {{ t("message.gbifRefreshIntro") }}
            <a href="https://www.gbif.org" target="_blank" rel="noopener">GBIF</a>.
        </p>

        <ProgressSpinner v-if="loading" />

        <template v-else-if="imports.length === 0">
            <p>{{ t("message.noDataImports") }}</p>
        </template>

        <template v-else>
            <h2 style="margin-top: 1.5rem; margin-bottom: 0.5rem;">{{ t("message.dataImports") }}</h2>

            <p>{{ t("message.mostRecentImportLabel") }}</p>

            <!-- Most recent import: full detail card -->
            <div style="border: 1px solid var(--p-surface-300); border-radius: 6px; padding: 1rem; margin-bottom: 1rem;">
                <div style="display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin-bottom: 0.75rem;">
                    <h3 style="margin: 0;">{{ imports[0].name }}</h3>
                    <a
                        v-if="imports[0].gbifDownloadId"
                        :href="gbifDownloadUrl(imports[0].gbifDownloadId)"
                        target="_blank"
                        rel="noopener"
                        style="white-space: nowrap; font-size: 0.875rem;"
                    >{{ t("message.gbifDownload") }} &rarr;</a>
                </div>
                <dl style="display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1.5rem; margin: 0;">
                    <dt style="font-weight: 600;">{{ t("message.dateTimeRange") }}</dt>
                    <dd style="margin: 0;">
                        {{ formatDateTime(imports[0].startTimestamp) }}
                        <template v-if="imports[0].endTimestamp">
                            &ndash; {{ formatDateTime(imports[0].endTimestamp) }}
                        </template>
                    </dd>

                    <dt style="font-weight: 600;">{{ t("message.importedObservations") }}</dt>
                    <dd style="margin: 0;">{{ imports[0].importedCount.toLocaleString(locale) }}</dd>

                    <dt style="font-weight: 600;">{{ t("message.newObservationsThisImport") }}</dt>
                    <dd style="margin: 0;">{{ imports[0].newObservationsCount.toLocaleString(locale) }}</dd>

                    <dt style="font-weight: 600;">{{ t("message.skippedObservations") }}</dt>
                    <dd style="margin: 0;">{{ imports[0].skippedCount.toLocaleString(locale) }}</dd>
                </dl>
            </div>

            <!-- Toggle for older imports -->
            <template v-if="imports.length > 1">
                <Button
                    :label="showAll ? t('message.hideDataImports') : t('message.showAllDataImports')"
                    severity="secondary"
                    size="small"
                    style="margin-bottom: 0.75rem;"
                    @click="showAll = !showAll"
                />

                <ul v-if="showAll" style="list-style: none; padding: 0; display: flex; flex-direction: column; gap: 0.5rem;">
                    <li
                        v-for="imp in imports.slice(1)"
                        :key="imp.id"
                        style="padding: 0.5rem 0.75rem; border: 1px solid var(--p-surface-200); border-radius: 6px;"
                    >
                        <strong>{{ imp.name }}</strong>
                        &ndash; {{ formatDateTime(imp.startTimestamp) }}
                        &ndash; {{ t("message.importedObservations") }}: {{ imp.importedCount.toLocaleString(locale) }}
                    </li>
                </ul>
            </template>
        </template>
    </div>
</template>
