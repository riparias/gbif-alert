<template>
  <div class="row">
    <div class="col-sm my-2">
      <bootstrap-alert
          v-if="showInProgressMessage"
          @clickClose="showInProgressMessage = false"
          alert-type="success"
          class="my-2"
      >
        <i class="bi bi-info-circle"></i>
        The observations are marked as seen in the background. This might take a
        couple of minutes if there are a lot of observations. Don't hesitate to
        refresh the page.
      </bootstrap-alert>

      <div class="row">
        <div class="col-2 d-flex align-items-center">
          <b>{{ $t("message.filters") }}</b>
        </div>

        <div class="col d-flex align-items-center">
          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.species')"
              :button-label-suffix-plural="$t('message.xSelectedSpecies')"
              :no-selection-button-label="$t('message.allSpecies')"
              :modal-title="$t('message.speciesToInclude')"
              :species-mode="true"
              :entries="availableSpeciesWithLabels"
              :initially-selected-entries-ids="filters.speciesIds"
              @entries-changed="changeSelectedSpecies"
          ></Filter-Selector>

          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.dataset')"
              :button-label-suffix-plural="$t('message.xSelectedDatasets')"
              :no-selection-button-label="$t('message.allDatasets')"
              :modal-title="$t('message.datasetsToInclude')"
              :entries="availableDatasetsAsEntries"
              :initially-selected-entries-ids="filters.datasetsIds"
              @entries-changed="changeSelectedDatasets"
          ></Filter-Selector>

          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.area')"
              :button-label-suffix-plural="$t('message.xSelectedAreas')"
              :no-selection-button-label="$t('message.everywhere')"
              :modal-title="$t('message.restrictToSpecificAreas')"
              :entries="availableAreasAsEntries"
              :initially-selected-entries-ids="filters.areaIds"
              @entries-changed="changeSelectedAreas"
          >
              <template v-slot:modal-body-top>
                  <div class="my-2">
                      <i class="bi bi-info-circle"></i>&nbsp;
                      <i18n-t keypath="message.customAreasInfoMessage" tag="false" for="message.customAreasLinkLabel">
                          <a :href="frontendConfig.apiEndpoints.myCustomAreasUrl">{{ $t('message.customAreasLinkLabel') }}</a>
                      </i18n-t>
                  </div>
              </template>
          </Filter-Selector>

          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.initialDataImport')"
              :button-label-suffix-plural="$t('message.xSelectedInitialDataImports')"
              :no-selection-button-label="$t('message.importedAnytime')"
              :modal-title="$t('message.firstImportedDuringDataImports')"
              :entries="availableDataimportsAsEntries"
              :initially-selected-entries-ids="filters.initialDataImportIds"
              @entries-changed="changeSelectedInitialDataImport"
          ></Filter-Selector>

          <ObservationStatusSelector
              v-if="frontendConfig.authenticatedUser"
              v-model="filters.status"
              :endpoints-urls="frontendConfig.apiEndpoints"
              :filters="filters"
              @markAsSeenQueued="showInProgressMessage = true"
          ></ObservationStatusSelector>
        </div>
      </div>
    </div>
  </div>
  <Observations
      :frontend-config="frontendConfig"
      :filters="filters"
      @selectedDateRangeUpdated="debouncedUpdateDateFilters"
  ></Observations>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {
  AreaInformation,
  DashboardFilters,
  DataImportInformation,
  DatasetInformation,
  DateRange,
  FrontEndConfig,
  SelectionEntry,
  SpeciesInformation, SpeciesInformationWithLabel,
} from "../../interfaces";
import axios from "axios";

import FilterSelector from "../FilterSelector.vue";
import ObservationStatusSelector from "../ObservationStatusSelector.vue";
import Observations from "../Observations.vue";
import BootstrapAlert from "../BootstrapAlert.vue";

import {debounce, DebouncedFunc} from "lodash";
import {dateTimeToFilterParam} from "../../helpers";
import SpeciesSelector from "../SpeciesSelector.vue";

declare const pteroisConfig: FrontEndConfig;
declare const initialFilters: DashboardFilters;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  availableDatasets: DatasetInformation[];
  availableAreas: AreaInformation[];
  availableDataImports: DataImportInformation[];
  filters: DashboardFilters;
  debouncedUpdateDateFilters: null | DebouncedFunc<(range: DateRange) => void>;
  showInProgressMessage: boolean;
}

export default defineComponent({
  name: "IndexPageRootComponent",

  components: {
    SpeciesSelector,
    BootstrapAlert,
    Observations,
    ObservationStatusSelector,
    FilterSelector,
  },
  data: function (): IndexPageRootComponentData {
    return {
      frontendConfig: pteroisConfig,

      availableSpecies: [],
      availableDatasets: [],
      availableAreas: [],
      availableDataImports: [],

      filters: initialFilters,

      debouncedUpdateDateFilters: null,
      showInProgressMessage: false,
    };
  },
  computed: {
    availableSpeciesWithLabels: function (): SpeciesInformationWithLabel[] {
      return this.availableSpecies.map((obj) => {
        return {
          ...obj,
          label: obj.scientificName,
        };
      });
    },

    availableDatasetsAsEntries: function (): SelectionEntry[] {
      return this.availableDatasets
          .sort((a, b) => (a.name.toLowerCase() > b.name.toLowerCase() ? 1 : -1))
          .map((d) => {
            return {id: d.id, label: d.name};
          });
    },
    availableAreasAsEntries: function (): SelectionEntry[] {
      return this.availableAreas
          .sort((a, b) => (a.name > b.name ? 1 : -1))
          .map((a: AreaInformation) => {
            let data: SelectionEntry = {id: a.id, label: a.name};
            if (a.isUserSpecific) {
              data.tags = [this.$t("message.custom")]
            }
            return data;
          });
    },
    availableDataimportsAsEntries: function (): SelectionEntry[] {
      return this.availableDataImports
          .sort((a, b) => (b.id > a.id ? 1 : -1))
          .map((d) => {
            return {id: d.id, label: d.str};
          });
    },
  },
  created() {
    // Approach stolen  from: https://dmitripavlutin.com/vue-debounce-throttle/
    this.debouncedUpdateDateFilters = debounce((range) => {
      this.filters.startDate = dateTimeToFilterParam(range.start);
      this.filters.endDate = dateTimeToFilterParam(range.end);
    }, 300);
  },
  beforeUnmount() {
    if (this.debouncedUpdateDateFilters) {
      this.debouncedUpdateDateFilters.cancel();
    }
  },
  methods: {
    changeSelectedSpecies: function (speciesIds: Number[]) {
      this.filters.speciesIds = speciesIds;
    },

    changeSelectedDatasets: function (datasetsIds: Number[]) {
      this.filters.datasetsIds = datasetsIds;
    },

    changeSelectedAreas: function (areasIds: Number[]) {
      this.filters.areaIds = areasIds;
    },
    changeSelectedInitialDataImport: function (dataImportsIds: Number[]) {
      this.filters.initialDataImportIds = dataImportsIds;
    },
    populateAvailableDatasets: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.datasetsListUrl)
          .then((response) => {
            this.availableDatasets = response.data;
          });
    },
    populateAvailableSpecies: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.speciesListUrl)
          .then((response) => {
            this.availableSpecies = response.data;
          });
    },
    populateAvailableAreas: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.areasListUrl)
          .then((response) => {
            this.availableAreas = response.data;
          });
    },
    populateAvailableDataImports: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.dataImportsListUrl)
          .then((response) => {
            this.availableDataImports = response.data;
          });
    },
  },

  mounted: function () {
    this.populateAvailableSpecies();
    this.populateAvailableDatasets();
    this.populateAvailableAreas();
    this.populateAvailableDataImports();
  },
});
</script>
