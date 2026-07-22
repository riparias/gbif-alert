<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import SpeciesName from "./SpeciesName.vue";
import { useAlertMeta } from "../composables/useAlertMeta";
import { useDisplayLabels } from "../composables/useDisplayLabels";
import { pickVernacular } from "../utils/vernacular";
import { pickByLocale } from "../utils/templateLabel";
import type { components } from "../types/api";

type AlertTemplateOut = components["schemas"]["AlertTemplateOut"];
type AlertOut = components["schemas"]["AlertOut"];

const props = defineProps<{
    template: AlertTemplateOut;
}>();

defineEmits<{
    use: [];
}>();

const { t, locale } = useI18n();
const { ensureAlertLabelsLoaded, datasetName, basisOfRecordName } = useDisplayLabels();

const expanded = ref(false);

const name = computed(() =>
    pickByLocale(props.template.nameEn, props.template.nameFr, props.template.nameNl, locale.value),
);

const description = computed(() =>
    pickByLocale(
        props.template.descriptionEn,
        props.template.descriptionFr,
        props.template.descriptionNl,
        locale.value,
    ),
);

// useAlertMeta expects a getter returning a full AlertOut, but only reads
// speciesDetails/areaIds/areaFilterMode/approachingDistanceKm to build
// areaDescription. AlertTemplateOut carries the same values for those fields,
// so we adapt it with harmless placeholders for the fields it doesn't have
// (name/emailNotificationsFrequency/notViewedCount/lastEmailSentAt) rather than
// re-implementing the area-formatting logic here.
const alertLike = computed<AlertOut>(() => ({
    id: props.template.id,
    name: name.value,
    speciesIds: props.template.speciesIds,
    datasetIds: props.template.datasetIds,
    basisOfRecordIds: props.template.basisOfRecordIds,
    areaIds: props.template.areaIds,
    emailNotificationsFrequency: "W",
    verifiedFilter: props.template.verifiedFilter,
    areaFilterMode: props.template.areaFilterMode,
    approachingDistanceKm: props.template.approachingDistanceKm,
    notViewedCount: 0,
    speciesDetails: props.template.speciesDetails,
    lastEmailSentAt: null,
}));

const { areaDescription } = useAlertMeta(() => alertLike.value);

const datasetNames = computed(() => props.template.datasetIds.map(datasetName).join(", "));

const basisOfRecordNames = computed(() =>
    props.template.basisOfRecordIds.map(basisOfRecordName).join(", "),
);

const verifiedFilterLabel = computed(() => {
    if (props.template.verifiedFilter === "verified") return t("message.verifiedOnly");
    if (props.template.verifiedFilter === "unverified") return t("message.unverifiedOnly");
    return t("message.all");
});

onMounted(() => {
    ensureAlertLabelsLoaded();
});
</script>

<template>
    <div class="template-card">
        <div class="template-card-body">
            <strong class="template-card-name">{{ name }}</strong>
            <p v-if="description" class="template-card-description">{{ description }}</p>
        </div>

        <div v-if="expanded" class="template-card-details">
            <div class="detail-row">
                <span class="detail-label">{{ t("message.filterSectionWhat") }}</span>
                <span class="detail-value detail-species">
                    <template v-if="template.speciesDetails.length">
                        <span
                            v-for="(sp, idx) in template.speciesDetails"
                            :key="sp.scientificName"
                            class="detail-species-item"
                        >
                            <SpeciesName
                                :scientific-name="sp.scientificName"
                                :vernacular-name="pickVernacular(sp, locale)"
                            /><template v-if="idx < template.speciesDetails.length - 1">,</template>
                        </span>
                    </template>
                    <template v-else>{{ t("message.allSpecies") }}</template>
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t("message.filterSectionWhere") }}</span>
                <span class="detail-value">{{ areaDescription || t("message.allAreas") }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t("message.dataset") }}</span>
                <span class="detail-value">{{ datasetNames || t("message.allDatasets") }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t("message.basisOfRecord") }}</span>
                <span class="detail-value">{{
                    basisOfRecordNames || t("message.allBasisOfRecord")
                }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t("message.filterSectionStatus") }}</span>
                <span class="detail-value">{{ verifiedFilterLabel }}</span>
            </div>
        </div>

        <div class="template-card-footer">
            <Button
                :label="t('message.useThisTemplate')"
                icon="pi pi-copy"
                size="small"
                @click="$emit('use')"
            />
            <button type="button" class="details-toggle" @click="expanded = !expanded">
                {{ t("message.templateDetails") }}
                <i :class="expanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" />
            </button>
        </div>
    </div>
</template>

<style scoped>
.template-card {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    border: 1px solid var(--p-content-border-color);
    border-radius: var(--p-content-border-radius);
    background: var(--p-content-background);
    /* Grid items default to min-width:auto, which lets wide content (e.g. a long
       species list) push the card past its track and overflow. Allow it to shrink. */
    min-width: 0;
}

.template-card-body {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.template-card-name {
    font-size: 0.95rem;
}

.template-card-description {
    margin: 0;
    font-size: 0.875rem;
    color: var(--p-text-muted-color);
}

.template-card-details {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--p-content-border-color);
}

.detail-row {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    font-size: 0.82rem;
}

.detail-label {
    font-weight: 600;
    color: var(--p-text-muted-color);
}

.detail-value {
    color: var(--p-text-color);
    overflow-wrap: anywhere;
}

/* Species render as a wrapping row of chips: each name stays intact (nowrap),
   but the list wraps to new lines instead of overflowing the card. */
.detail-species {
    display: flex;
    flex-wrap: wrap;
    column-gap: 0.4rem;
    row-gap: 0.15rem;
}

.detail-species-item {
    white-space: nowrap;
}

.template-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: auto;
}

.details-toggle {
    all: unset;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.82rem;
    color: var(--p-primary-color);
}

.details-toggle:hover {
    text-decoration: underline;
}
</style>
