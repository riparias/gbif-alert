<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Card from "primevue/card";
import InputText from "primevue/inputtext";
import MultiSelect from "primevue/multiselect";
import Select from "primevue/select";
import InputNumber from "primevue/inputnumber";
import Message from "primevue/message";
import type { components } from "../types/api";

type SpeciesOut = components["schemas"]["SpeciesOut"];
type DatasetOut = components["schemas"]["DatasetOut"];
type AreaOut = components["schemas"]["AreaOut"];
type BasisOfRecordOut = components["schemas"]["BasisOfRecordOut"];
type AlertNotificationFrequencyOut = components["schemas"]["AlertNotificationFrequencyOut"];

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();

// Create mode when no alertId param; edit mode when alertId is present.
const alertId = route.params.alertId ? Number(route.params.alertId) : null;
const isEditMode = alertId !== null;

function getCsrf(): string {
    return (document.cookie.match(/csrftoken=([^;]+)/) ?? [])[1] ?? "";
}

// Available options loaded from API
const speciesOptions = ref<SpeciesOut[]>([]);
const datasetOptions = ref<DatasetOut[]>([]);
const areaOptions = ref<AreaOut[]>([]);
const basisOfRecordOptions = ref<BasisOfRecordOut[]>([]);
const frequencyOptions = ref<AlertNotificationFrequencyOut[]>([]);

// Form fields
const name = ref("");
const selectedSpeciesIds = ref<number[]>([]);
const selectedDatasetIds = ref<number[]>([]);
const selectedAreaIds = ref<number[]>([]);
const selectedBasisOfRecordIds = ref<number[]>([]);
const emailNotificationsFrequency = ref("W");
const verifiedFilter = ref("all");
const areaFilterMode = ref("inside");
const approachingDistanceKm = ref<number | null>(null);

// Server-side validation errors keyed by field name
const errors = ref<Record<string, string[]>>({});
const saving = ref(false);

const areaFilterModeOptions = computed(() => [
    { id: "inside", label: t("message.areaFilterModeInside") },
    { id: "approaching", label: t("message.areaFilterModeApproaching") },
    { id: "both", label: t("message.areaFilterModeBoth") },
]);

const verifiedFilterOptions = computed(() => [
    { id: "all", label: t("message.all") },
    { id: "verified", label: t("message.verifiedOnly") },
    { id: "unverified", label: t("message.unverifiedOnly") },
]);

// Show approaching distance input only when mode requires it and areas are selected
const showApproachingDistance = computed(
    () =>
        selectedAreaIds.value.length > 0 &&
        (areaFilterMode.value === "approaching" || areaFilterMode.value === "both")
);

async function loadOptions() {
    const [species, datasets, areas, basisOfRecord, frequencies] = await Promise.all([
        fetch("/api/v2/species/").then((r) => r.json()),
        fetch("/api/v2/datasets/").then((r) => r.json()),
        fetch("/api/v2/areas/").then((r) => r.json()),
        fetch("/api/v2/basis-of-record/").then((r) => r.json()),
        fetch("/api/v2/alerts/notification-frequencies/").then((r) => r.json()),
    ]);
    speciesOptions.value = species;
    datasetOptions.value = datasets;
    areaOptions.value = areas;
    basisOfRecordOptions.value = basisOfRecord;
    frequencyOptions.value = frequencies;
}

async function loadAlertData() {
    const res = await fetch(`/api/v2/alerts/${alertId}/`);
    const data = await res.json();
    name.value = data.name;
    selectedSpeciesIds.value = data.speciesIds;
    selectedDatasetIds.value = data.datasetIds;
    selectedAreaIds.value = data.areaIds;
    selectedBasisOfRecordIds.value = data.basisOfRecordIds;
    emailNotificationsFrequency.value = data.emailNotificationsFrequency;
    verifiedFilter.value = data.verifiedFilter;
    areaFilterMode.value = data.areaFilterMode;
    approachingDistanceKm.value = data.approachingDistanceKm;
}

async function suggestName() {
    const res = await fetch("/api/v2/alerts/suggest-name/");
    name.value = (await res.json()).name;
}

const navConfig = JSON.parse(
    document.getElementById("gbif-alert-nav-config")!.textContent!
);

onMounted(async () => {
    await loadOptions();
    if (isEditMode) {
        document.title = `${t("message.editAlert")} - ${navConfig.siteName}`;
        await loadAlertData();
    } else {
        document.title = `${t("message.createAlert")} - ${navConfig.siteName}`;
        await suggestName();
    }
});

async function save() {
    saving.value = true;
    errors.value = {};

    const payload = {
        name: name.value,
        speciesIds: selectedSpeciesIds.value,
        datasetIds: selectedDatasetIds.value,
        areaIds: selectedAreaIds.value,
        basisOfRecordIds: selectedBasisOfRecordIds.value,
        emailNotificationsFrequency: emailNotificationsFrequency.value,
        verifiedFilter: verifiedFilter.value,
        areaFilterMode: areaFilterMode.value,
        approachingDistanceKm: approachingDistanceKm.value,
    };

    try {
        const url = isEditMode ? `/api/v2/alerts/${alertId}/` : "/api/v2/alerts/";
        const method = isEditMode ? "PUT" : "POST";
        const res = await fetch(url, {
            method,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrf(),
            },
            body: JSON.stringify(payload),
        });

        if (res.status === 200 || res.status === 201) {
            const data = await res.json();
            toast.add({
                severity: "success",
                summary: t("message.alertSuccessfullySaved"),
                life: 3000,
            });
            router.push(`/alert/${data.id}`);
        } else {
            const data = await res.json();
            errors.value = data.errors ?? {};
        }
    } finally {
        saving.value = false;
    }
}
</script>

<template>
    <div class="alert-form-page">
        <div class="page-header">
            <h1>{{ isEditMode ? t("message.editAlert") : t("message.createAlert") }}</h1>
            <Button
                :label="t('message.backToAlertsList')"
                icon="pi pi-arrow-left"
                link
                @click="router.push('/my-alerts')"
            />
        </div>

        <Card>
            <template #content>
                <div class="form-field">
                    <label for="alert-name">{{ t("message.alertName") }} *</label>
                    <InputText id="alert-name" v-model="name" class="w-full" />
                    <Message v-if="errors.name" severity="error" :closable="false" size="small">
                        {{ errors.name.join(", ") }}
                    </Message>
                </div>

                <div class="form-field">
                    <label>{{ t("message.speciesToInclude") }} *</label>
                    <p class="field-hint">{{ t("message.atLeastOneSpeciesMustBeSelected") }}</p>
                    <MultiSelect
                        v-model="selectedSpeciesIds"
                        :options="speciesOptions"
                        option-label="scientificName"
                        option-value="id"
                        filter
                        :placeholder="t('message.allSpecies')"
                        class="w-full"
                    />
                    <Message v-if="errors.species" severity="error" :closable="false" size="small">
                        {{ errors.species.join(", ") }}
                    </Message>
                </div>

                <div class="form-field">
                    <label>{{ t("message.areasToInclude") }}</label>
                    <p class="field-hint">{{ t("message.noAreaSelection") }}</p>
                    <MultiSelect
                        v-model="selectedAreaIds"
                        :options="areaOptions"
                        option-label="name"
                        option-value="id"
                        filter
                        :placeholder="t('message.everywhere')"
                        class="w-full"
                    />
                </div>

                <div v-if="selectedAreaIds.length > 0" class="form-field">
                    <label>{{ t("message.areaFilterMode") }}</label>
                    <Select
                        v-model="areaFilterMode"
                        :options="areaFilterModeOptions"
                        option-label="label"
                        option-value="id"
                        class="w-full"
                    />
                    <Message
                        v-if="errors.area_filter_mode"
                        severity="error"
                        :closable="false"
                        size="small"
                    >
                        {{ errors.area_filter_mode.join(", ") }}
                    </Message>
                </div>

                <div v-if="showApproachingDistance" class="form-field">
                    <label for="approaching-distance">
                        {{ t("message.approachingDistanceKm") }}
                    </label>
                    <InputNumber
                        id="approaching-distance"
                        v-model="approachingDistanceKm"
                        :min="0.1"
                        :max="50"
                        :step="0.1"
                        :min-fraction-digits="1"
                        :max-fraction-digits="1"
                        class="w-full"
                    />
                    <Message
                        v-if="errors.approaching_distance_km"
                        severity="error"
                        :closable="false"
                        size="small"
                    >
                        {{ errors.approaching_distance_km.join(", ") }}
                    </Message>
                </div>

                <div class="form-field">
                    <label>{{ t("message.datasetsToInclude") }}</label>
                    <p class="field-hint">{{ t("message.noDatasetSelection") }}</p>
                    <MultiSelect
                        v-model="selectedDatasetIds"
                        :options="datasetOptions"
                        option-label="name"
                        option-value="id"
                        filter
                        :placeholder="t('message.allDatasets')"
                        class="w-full"
                    />
                </div>

                <div class="form-field">
                    <label>{{ t("message.basisOfRecordToInclude") }}</label>
                    <p class="field-hint">{{ t("message.noBasisOfRecordSelection") }}</p>
                    <MultiSelect
                        v-model="selectedBasisOfRecordIds"
                        :options="basisOfRecordOptions"
                        option-label="name"
                        option-value="id"
                        :placeholder="t('message.allBasisOfRecord')"
                        class="w-full"
                    />
                </div>

                <div class="form-field">
                    <label>{{ t("message.verificationFilter") }}</label>
                    <Select
                        v-model="verifiedFilter"
                        :options="verifiedFilterOptions"
                        option-label="label"
                        option-value="id"
                        class="w-full"
                    />
                </div>

                <div class="form-field">
                    <label>{{ t("message.alertNotificationsFrequency") }}</label>
                    <Select
                        v-model="emailNotificationsFrequency"
                        :options="frequencyOptions"
                        option-label="label"
                        option-value="id"
                        class="w-full"
                    />
                </div>

                <div class="form-actions">
                    <Button
                        :label="isEditMode ? t('message.save') : t('message.createAlert')"
                        :loading="saving"
                        @click="save"
                    />
                    <Button
                        :label="t('message.backToAlertsList')"
                        severity="secondary"
                        @click="router.push('/my-alerts')"
                    />
                </div>
            </template>
        </Card>
    </div>
</template>

<style scoped>
.alert-form-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    max-width: 720px;
    margin: 0 auto;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.page-header h1 {
    margin: 0;
}

.form-field {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin-bottom: 1.25rem;
}

.form-field label {
    font-weight: 600;
}

.field-hint {
    margin: 0;
    font-size: 0.875rem;
    color: var(--p-text-muted-color);
}

.form-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
}

.w-full {
    width: 100%;
}
</style>
