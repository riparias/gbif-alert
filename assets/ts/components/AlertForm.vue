<template>
  <div id="pterois-alert-successfully-saved" v-if="successfullySaved">
    <p>{{ $t('message.alertSuccessfullySaved') }}</p>
  </div>

  <div v-else>
    <BootstrapAlert alert-type="danger" v-show="hasErrors" :dismissible="false">
      <i class="bi bi-sign-stop-fill"></i> <span ref="hasErrorsParagraph">{{ $t("message.pleaseFixErrors") }}</span>
    </BootstrapAlert>

    <ul class="list-unstyled">
      <li class="pterois-form-error" v-for="error in globalErrors">{{ error }}</li>
    </ul>

    <div class="mb-3">
      <h3><label for="alertName" class="form-label">{{ $t("message.alertName") }}*</label></h3>
      <div class="row">
        <div class="col offset-md-1">
          <ul class="list-unstyled">
            <li class="pterois-form-error" v-for="error in nameErrors">{{ error }}</li>
          </ul>
          <input type="text" v-model="alertData.name" class="form-control" id="alertName">
        </div>
      </div>
    </div>

    <div id="pterois-alert-species-selection" class="mb-3">
      <h3><label class="form-label">{{ $t("message.speciesToInclude") }}*</label></h3>
      <div class="col offset-md-1">
        <ul class="list-unstyled">
          <li class="pterois-form-error" v-for="error in speciesErrors">{{ error }}</li>
        </ul>
        <BootstrapAlert :dismissible="false" alert-type="info">
          <i class="bi bi-info-circle-fill"></i> {{ $t("message.atLeastOneSpeciesMustBeSelected") }}
        </BootstrapAlert>
        <Selector :available-entries="availableSpeciesAsDataRows" :columns-config="[
                  {label: $t('message.scientificName'), dataIndex: 0, formatter: scientificNameFormatter },
                  {label: $t('message.vernacularName'), dataIndex: 1},
                  {label: $t('message.gbifTaxonKey'), dataIndex: 2, formatter: gbifTaxonKeyFormatter }]"
                  v-model="alertData.speciesIds"></Selector>
      </div>
    </div>

    <div id="pterois-alert-areas-selection" class="mb-3">
      <h3><label class="form-label">{{ $t("message.areasToInclude") }}</label></h3>
      <div class="col offset-md-1">
        <BootstrapAlert :dismissible="false" alert-type="info">
          <i class="bi bi-info-circle-fill"></i> {{ $t("message.noAreaSelection") }}
        </BootstrapAlert>
        <Selector :available-entries="availableAreasAsDataRows"
                  :columns-config="[
                    {label: $t('message.name'), dataIndex: 0},
                    {label: $t('message.areaType'), dataIndex: 1}
                  ]" v-model="alertData.areaIds"></Selector>
      </div>
    </div>

    <div id="pterois-alert-datasets-selection" class="mb-3">
      <h3><label class="form-label">{{ $t("message.datasetsToInclude") }}</label></h3>
      <div class="col offset-md-1">
        <BootstrapAlert :dismissible="false" alert-type="info">
          <i class="bi bi-info-circle-fill"></i> {{ $t("message.noDatasetSelection") }}
        </BootstrapAlert>
        <Selector :available-entries="availableDatasetsAsDataRows"
                  :columns-config="[
                      {label: $t('message.name'), dataIndex: 0},
                      {label: $t('message.gbifDatasetKey'), dataIndex: 1, formatter: gbifDatasetKeyFormatter }
                  ]"
                  v-model="alertData.datasetIds"></Selector>
      </div>
    </div>


    <div id="pterois-alert-frequency-selection" class="mb-3">
      <h3><label class="form-label">{{ $t("message.alertNotificationsFrequency") }}</label></h3>
      <div class="col offset-md-1">
        <select id="pterois-alert-frequency-select" v-model="alertData.emailNotificationsFrequency" class="form-select">
          <option v-for="frequency in availableNotificationFrequencies" :value="frequency.id">{{
              frequency.label
            }}
          </option>
        </select>
      </div>
    </div>

  </div>

  <div>
    <a class="btn btn-primary btn-sm" v-if="successfullySaved"
       :href="alertDetailsPageUrl">{{ $t('message.viewAlertObservations') }}</a>
    <input v-else class="btn btn-primary btn-sm" type="submit"
           :value="newAlert ? $t('message.createAlert') : $t('message.save')"
           id="pterois-alert-save-btn" @click="submit()">
    <a :href="props.alertsListPageUrl" class="btn btn-secondary btn-sm mx-2">{{ $t('message.backToAlertsList') }}</a>
  </div>

</template>

<script setup lang="ts">
import {computed, onMounted, ref} from "vue";
import axios from "axios";

import {AreaInformation, DataRow, DatasetInformation, FrontEndConfig, SpeciesInformation} from "../interfaces";
import Selector from "./Selector.vue";
import BootstrapAlert from "./BootstrapAlert.vue";
import {
  gbifDatasetKeyFormatter,
  gbifTaxonKeyFormatter,
  prepareAreasData,
  prepareDatasetsData,
  prepareSpeciesData,
  scientificNameFormatter
} from "../helpers";
import {useI18n} from "vue-i18n";

interface Props {
  alertUrl: string
  alertsListPageUrl: string
  speciesListUrl: string,
  areasListUrl: string;
  datasetsListUrl: string;
  suggestAlertNameUrl?: string; // Not necessary if editing an existing alert
  notificationsFrequenciesUrl: string;
  alertId?: number // If set, we want to update rather than create
}

interface FrequencyInformation {
  id: number;
  label: string;
}

declare const pteroisConfig: FrontEndConfig;
const {t} = useI18n();

const props = withDefaults(defineProps<Props>(), {});

const availableSpecies = ref<SpeciesInformation[]>([]);
const availableAreas = ref<AreaInformation[]>([]);
const availableDatasets = ref<DatasetInformation[]>([]);

const availableNotificationFrequencies = ref<FrequencyInformation[]>([]);

const hasErrorsParagraph = ref<HTMLElement | null>(null);

// alert data
const alertData = ref({
  id: props.alertId,
  name: '',
  speciesIds: [],
  datasetIds: [],
  areaIds: [],
  emailNotificationsFrequency: 'W'
});


const alertIdFromServer = ref<number | null>(null);

const newAlert = computed(() => props.alertId == null) // true if creating a new alert, false if editing an existing one
const successfullySaved = ref<boolean>(false);

// Backend-reported errors
const nameErrors = ref<string[]>([]);
const speciesErrors = ref<string[]>([]);
const globalErrors = ref<string[]>([]);
const hasErrors = computed(() => [...nameErrors.value, ...speciesErrors.value, ...globalErrors.value].length > 0);

const alertDetailsPageUrl = computed(() => {
  return pteroisConfig.apiEndpoints.alertPageUrlTemplate.replace('{id}', alertIdFromServer.value!.toString());
});

const getAlertNameSuggestion = function () {
  axios.get(props.suggestAlertNameUrl!).then((response) => {
    alertData.value.name = response.data.name;
  })
}

const populateAlertData = function () {
  axios.get(props.alertUrl, {params: {alert_id: props.alertId}}).then((response) => {
    alertData.value = response.data;
  })
}

const populateAvailableSpecies = function () {
  axios
      .get(props.speciesListUrl)
      .then((response) => {
        availableSpecies.value = response.data;
      });
}

const populateAvailableAreas = function () {
  axios
      .get(props.areasListUrl)
      .then((response) => {
        availableAreas.value = response.data;
      })
}

const populateAvailableDatasets = function () {
  axios
      .get(props.datasetsListUrl)
      .then((response) => {
        availableDatasets.value = response.data;
      })
}

const populateAvailableNotificationFrequencies = function () {
  axios
      .get(props.notificationsFrequenciesUrl)
      .then((response) => {
        availableNotificationFrequencies.value = response.data;
      })
}


const availableAreasAsDataRows = computed(
    (): DataRow[] => {
      return prepareAreasData(availableAreas.value, t);
    },
);

const availableDatasetsAsDataRows = computed(
    (): DataRow[] => {
      return prepareDatasetsData(availableDatasets.value);
    },
);

const availableSpeciesAsDataRows = computed(
    (): DataRow[] => {
      return prepareSpeciesData(availableSpecies.value);
    },
);

onMounted(() => {
  // Populate initial values if editing an existing alert
  populateAvailableSpecies();
  populateAvailableAreas();
  populateAvailableDatasets();

  populateAvailableNotificationFrequencies();

  if (!newAlert.value) {
    populateAlertData();
  } else {
    getAlertNameSuggestion();
  }
})

const submit = function () {
  const headers = {"X-CSRFToken": (window as any).CSRF_TOKEN};

  axios.post(props.alertUrl, alertData.value, {headers: headers}).then((response) => {
    alertIdFromServer.value = response.data.alertId;
    successfullySaved.value = response.data.success;
    if (successfullySaved.value !== true) {
      nameErrors.value = response.data.errors.name || [];
      speciesErrors.value = response.data.errors.species || [];
      globalErrors.value = response.data.errors['__all__'] || [];
      scrollToError();
    }
  })
}

const scrollToError = function () {
  const element = hasErrorsParagraph.value;
  window.scrollTo(0, element!.scrollHeight)
}

</script>

<style>
/* Unfortunately we cannot scope the style due to https://github.com/vuejs/vue-loader/issues/1915 */
.pterois-form-error {
  color: red;
}
</style>