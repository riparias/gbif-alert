<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import type { components } from "../types/api";

type DataImportOut = components["schemas"]["DataImportOut"];
type SkippedReasonOut = components["schemas"]["SkippedReasonOut"];

const props = defineProps<{ dataImport: DataImportOut }>();

const { t, locale } = useI18n();

// A Record over the API's reason union, so a new reason without a label fails
// the type check.
const REASON_LABEL_KEYS: Record<SkippedReasonOut["reason"], string> = {
    missing_basis_of_record: "message.skipReasonMissingBasisOfRecord",
    missing_coordinates: "message.skipReasonMissingCoordinates",
    missing_occurrence_id: "message.skipReasonMissingOccurrenceId",
    missing_year: "message.skipReasonMissingYear",
    occurrence_status_not_present: "message.skipReasonOccurrenceStatusNotPresent",
};

const showSkipped = ref(false);
// undefined: not fetched yet; null: the import predates the recorded details
const skipped = ref<SkippedReasonOut[] | null | undefined>(undefined);

// A row failing several rules is listed under each, so the lists can add up to
// more than the count shown just above them.
const listedRowsExceedCount = computed(
    () =>
        (skipped.value ?? []).reduce((n, entry) => n + entry.gbifIds.length, 0) >
        props.dataImport.skippedCount,
);

function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString(locale.value);
}

async function toggleSkipped() {
    showSkipped.value = !showSkipped.value;
    // Fetched on demand: it can list thousands of rows, and the page shows
    // every import ever made.
    if (showSkipped.value && skipped.value === undefined) {
        const resp = await fetch(
            `/api/v2/data-imports/${props.dataImport.id}/skipped-observations/`,
        );
        if (resp.ok) {
            skipped.value = await resp.json();
        }
    }
}
</script>

<template>
    <dl class="data-import-details">
        <dt>{{ t("message.dateTimeRange") }}</dt>
        <dd>
            {{ formatDateTime(dataImport.startedAt) }}
            <template v-if="dataImport.endedAt">
                &ndash; {{ formatDateTime(dataImport.endedAt) }}
            </template>
        </dd>

        <dt>{{ t("message.importedObservations") }}</dt>
        <dd>{{ dataImport.importedCount.toLocaleString(locale) }}</dd>

        <dt>{{ t("message.newObservationsThisImport") }}</dt>
        <dd>{{ dataImport.newObservationsCount.toLocaleString(locale) }}</dd>

        <dt>{{ t("message.skippedObservations") }}</dt>
        <dd>
            <span>{{ dataImport.skippedCount.toLocaleString(locale) }}</span>
            <Button
                v-if="dataImport.skippedCount > 0"
                :label="
                    showSkipped ? t('message.hideSkippedDetails') : t('message.showSkippedDetails')
                "
                link
                size="small"
                class="skipped-toggle"
                @click="toggleSkipped"
            />
            <div v-if="showSkipped && skipped !== undefined" class="skipped-details">
                <p v-if="skipped === null">{{ t("message.skippedDetailsNotRecorded") }}</p>
                <template v-else>
                    <details v-for="entry in skipped" :key="entry.reason">
                        <summary>
                            {{ t(REASON_LABEL_KEYS[entry.reason]) }}
                            ({{ entry.gbifIds.length.toLocaleString(locale) }})
                        </summary>
                        <div class="skipped-ids">
                            <a
                                v-for="gbifId in entry.gbifIds"
                                :key="gbifId"
                                :href="`https://www.gbif.org/occurrence/${gbifId}`"
                                target="_blank"
                                rel="noopener"
                                >{{ gbifId }}</a
                            >
                        </div>
                    </details>
                    <p v-if="listedRowsExceedCount" class="skipped-note">
                        {{ t("message.skippedDetailsOverlapNote") }}
                    </p>
                </template>
            </div>
        </dd>
    </dl>
</template>

<style scoped>
.data-import-details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1.5rem;
    margin: 0;
}

.data-import-details dt {
    font-weight: 600;
}

.data-import-details dd {
    margin: 0;
}

.skipped-toggle {
    padding-block: 0;
}

.skipped-details {
    margin-top: 0.5rem;
}

.skipped-details summary {
    cursor: pointer;
}

.skipped-ids {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.75rem;
    margin: 0.25rem 0 0.5rem 1rem;
    font-size: 0.875rem;
}

.skipped-note {
    margin: 0.25rem 0 0;
    font-size: 0.875rem;
    color: var(--p-text-muted-color);
}
</style>
