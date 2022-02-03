<template>
  <div class="row">
    <div class="col-sm my-2">
      <div class="row">
        <div class="col-2">
          <b>Data filtering:</b>
        </div>

        <div class="col-7">
          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="species"
            button-label-plural="species"
            modal-title="Species to include"
            :entries="availableSpeciesAsEntries"
            @entries-changed="changeSelectedSpecies"
          ></Modal-Multi-Selector>

          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="dataset"
            button-label-plural="datasets"
            modal-title="Datasets to include"
            :entries="availableDatasetsAsEntries"
            @entries-changed="changeSelectedDatasets"
          ></Modal-Multi-Selector>

          <Modal-Multi-Selector
            class="m-2"
            button-label-singular="area"
            button-label-plural="areas"
            no-selection-button-label="Everywhere"
            modal-title="Restrict to specific areas"
            :entries="availableAreasAsEntries"
            @entries-changed="changeSelectedAreas"
          ></Modal-Multi-Selector>

          <ObservationStatusSelector
            v-if="frontendConfig.authenticatedUser"
            v-model="filters.status"
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
} from "../../interfaces";
import axios from "axios";

import ModalMultiSelector from "../ModalMultiSelector.vue";

import ObservationStatusSelector from "../ObservationStatusSelector.vue";
import Observations from "../Observations.vue";
import { DateTime } from "luxon";
import { debounce, DebouncedFunc } from "lodash";
import { dateTimeToFilterParam } from "../../helpers";

declare const ripariasConfig: FrontEndConfig;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  availableDatasets: DatasetInformation[];
  availableAreas: AreaInformation[];
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

      filters: {
        speciesIds: [],
        datasetsIds: [],
        areaIds: [],
        startDate: null,
        endDate: null,
        status: null,
      },

      debouncedUpdateDateFilters: null,
    };
  },
  computed: {
    availableSpeciesAsEntries: function (): SelectionEntry[] {
      return this.availableSpecies.map((s: SpeciesInformation) => {
        return { id: s.id, label: s.scientificName };
      });
    },
    availableDatasetsAsEntries: function (): SelectionEntry[] {
      return this.availableDatasets.map((d: DatasetInformation) => {
        return { id: d.id, label: d.name };
      });
    },
    availableAreasAsEntries: function (): SelectionEntry[] {
      return this.availableAreas.map((a: AreaInformation) => {
        return { id: a.id, label: a.name };
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
  },

  mounted: function () {
    this.populateAvailableSpecies();
    this.populateAvailableDatasets();
    this.populateAvailableAreas();
  },
});
</script>
