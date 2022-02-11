<template>
  <div class="row">
    <div class="col-sm my-2">
      <div class="row">
        <div class="col-2">
          <b>Data filtering:</b>
        </div>

        <div class="col">
          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="species"
            button-label-plural="species"
            modal-title="Species to include"
            :entries="availableSpeciesAsEntries"
            :initially-selected-entries-ids="filters.speciesIds"
            @entries-changed="changeSelectedSpecies"
          ></Modal-Multi-Selector>

          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="dataset"
            button-label-plural="datasets"
            modal-title="Datasets to include"
            :entries="availableDatasetsAsEntries"
            :initially-selected-entries-ids="filters.datasetsIds"
            @entries-changed="changeSelectedDatasets"
          ></Modal-Multi-Selector>

          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="area"
            button-label-plural="areas"
            no-selection-button-label="Everywhere"
            modal-title="Restrict to specific areas"
            :entries="availableAreasAsEntries"
            :initially-selected-entries-ids="filters.areaIds"
            @entries-changed="changeSelectedAreas"
          ></Modal-Multi-Selector>

          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="initial data import"
            button-label-plural="initial data imports"
            no-selection-button-label="Imported at all time"
            modal-title="First imported during data imports"
            :entries="availableDataimportsAsEntries"
            :initially-selected-entries-ids="filters.initialDataImportIds"
            @entries-changed="changeSelectedInitialDataImport"
          ></Modal-Multi-Selector>

          <ObservationStatusSelector
            v-if="frontendConfig.authenticatedUser"
            v-model="filters.status"
            :counter-url="frontendConfig.apiEndpoints.observationsCounterUrl"
            :filters="filters"
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
import { defineComponent } from "vue";
import {
  DashboardFilters,
  DatasetInformation,
  SpeciesInformation,
  FrontEndConfig,
  SelectionEntry,
  AreaInformation,
  DateRange,
  DataImportInformation,
} from "../../interfaces";
import axios from "axios";

import ModalMultiSelector from "../ModalMultiSelector.vue";

import ObservationStatusSelector from "../ObservationStatusSelector.vue";
import Observations from "../Observations.vue";
import { debounce, DebouncedFunc } from "lodash";
import { dateTimeToFilterParam } from "../../helpers";

declare const ripariasConfig: FrontEndConfig;
declare const initialFilters: DashboardFilters;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  availableDatasets: DatasetInformation[];
  availableAreas: AreaInformation[];
  availableDataImports: DataImportInformation[];
  filters: DashboardFilters;
  debouncedUpdateDateFilters: null | DebouncedFunc<(range: DateRange) => void>;
}

export default defineComponent({
  name: "IndexPageRootComponent",
  components: {
    Observations,
    ObservationStatusSelector,
    ModalMultiSelector,
  },
  data: function (): IndexPageRootComponentData {
    return {
      frontendConfig: ripariasConfig,

      availableSpecies: [],
      availableDatasets: [],
      availableAreas: [],
      availableDataImports: [],

      filters: initialFilters,

      debouncedUpdateDateFilters: null,
    };
  },
  computed: {
    availableSpeciesAsEntries: function (): SelectionEntry[] {
      return this.availableSpecies
        .sort((a, b) => (a.scientificName > b.scientificName ? 1 : -1))
        .map((s) => {
          return { id: s.id, label: s.scientificName };
        });
    },
    availableDatasetsAsEntries: function (): SelectionEntry[] {
      return this.availableDatasets
        .sort((a, b) => (a.name.toLowerCase() > b.name.toLowerCase() ? 1 : -1))
        .map((d) => {
          return { id: d.id, label: d.name };
        });
    },
    availableAreasAsEntries: function (): SelectionEntry[] {
      return this.availableAreas
        .sort((a, b) => (a.name > b.name ? 1 : -1))
        .map((a: AreaInformation) => {
          return { id: a.id, label: a.name };
        });
    },
    availableDataimportsAsEntries: function (): SelectionEntry[] {
      return this.availableDataImports
        .sort((a, b) => (a.str > b.str ? 1 : -1))
        .map((d) => {
          return { id: d.id, label: d.str };
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
