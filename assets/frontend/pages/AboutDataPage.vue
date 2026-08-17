<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Accordion from "primevue/accordion";
import AccordionPanel from "primevue/accordionpanel";
import AccordionHeader from "primevue/accordionheader";
import AccordionContent from "primevue/accordioncontent";
import Button from "primevue/button";
import ProgressSpinner from "primevue/progressspinner";
import DataImportDetails from "../components/DataImportDetails.vue";
import type { components } from "../types/api";

type DataImportOut = components["schemas"]["DataImportOut"];

const { t, locale } = useI18n();
const imports = ref<DataImportOut[]>([]);
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
        <h1 style="margin-bottom: 1rem">{{ t("message.aboutData") }}</h1>

        <p>
            {{ t("message.gbifRefreshIntro") }}
            <a href="https://www.gbif.org" target="_blank" rel="noopener">GBIF</a>.
        </p>

        <ProgressSpinner v-if="loading" />

        <template v-else-if="imports.length === 0">
            <p>{{ t("message.noDataImports") }}</p>
        </template>

        <template v-else>
            <h2 style="margin-top: 1.5rem; margin-bottom: 0.5rem">
                {{ t("message.dataImports") }}
            </h2>

            <p>{{ t("message.mostRecentImportLabel") }}</p>

            <!-- Most recent import: details are always expanded -->
            <div
                style="
                    border: 1px solid var(--p-surface-300);
                    border-radius: 6px;
                    padding: 1rem;
                    margin-bottom: 1rem;
                "
            >
                <div
                    style="
                        display: flex;
                        align-items: baseline;
                        justify-content: space-between;
                        gap: 1rem;
                        margin-bottom: 0.75rem;
                    "
                >
                    <h3 style="margin: 0">{{ imports[0].name }}</h3>
                    <a
                        v-if="imports[0].gbifDownloadId"
                        :href="gbifDownloadUrl(imports[0].gbifDownloadId)"
                        target="_blank"
                        rel="noopener"
                        style="white-space: nowrap; font-size: 0.875rem"
                        >{{ t("message.gbifDownload") }} &rarr;</a
                    >
                </div>
                <DataImportDetails :data-import="imports[0]" />
            </div>

            <!-- Older imports: a summary line each, expandable to the same details -->
            <template v-if="imports.length > 1">
                <Button
                    :label="
                        showAll ? t('message.hideDataImports') : t('message.showAllDataImports')
                    "
                    severity="secondary"
                    size="small"
                    style="margin-bottom: 0.75rem"
                    @click="showAll = !showAll"
                />

                <Accordion v-if="showAll" multiple>
                    <AccordionPanel v-for="imp in imports.slice(1)" :key="imp.id" :value="imp.id">
                        <AccordionHeader>
                            <span>
                                <strong>{{ imp.name }}</strong>
                                &ndash; {{ formatDateTime(imp.startedAt) }} &ndash;
                                {{ t("message.importedObservations") }}:
                                {{ imp.importedCount.toLocaleString(locale) }}
                            </span>
                        </AccordionHeader>
                        <AccordionContent>
                            <DataImportDetails :data-import="imp" />
                            <a
                                v-if="imp.gbifDownloadId"
                                :href="gbifDownloadUrl(imp.gbifDownloadId)"
                                target="_blank"
                                rel="noopener"
                                style="display: inline-block; margin-top: 0.75rem"
                                >{{ t("message.gbifDownload") }} &rarr;</a
                            >
                        </AccordionContent>
                    </AccordionPanel>
                </Accordion>
            </template>
        </template>
    </div>
</template>
