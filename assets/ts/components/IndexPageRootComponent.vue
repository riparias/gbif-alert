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

          <div
            class="row mb-3"
            v-if="frontendConfig.authenticatedUser === true"
          >
            <label
              for="obsStatus"
              class="col-sm-2 col-form-label col-form-label-sm"
              >Status</label
            >
            <div class="col-sm-10">
              <select
                class="form-control form-control-sm"
                id="obsStatus"
                placeholder="col-form-label-sm"
                v-model="filters.status"
              >
                <option :value="null">All</option>
                <option value="seen">Seen</option>
                <option value="unseen">Unseen</option>
              </select>
            </div>
          </div>
        </div>

        <div class="col-3">
          <Observations-counter
            class="float-right"
            :counter-url="frontendConfig.apiEndpoints.observationsCounterUrl"
            :filters="filters"
          ></Observations-counter>
        </div>
      </div>
    </div>
  </div>

  <div class="row">
    <div class="col">
      <Custom-observations-time-line
        :filters="filters"
        :histogram-data-url="
          frontendConfig.apiEndpoints.observationsHistogramDataUrl
        "
        @selectedDateRangeUpdated="debouncedUpdateDateFilters"
      />
    </div>
  </div>
  <hr />

  <div class="row">
    <div class="col">
      <Tab-switcher
        v-model="selectedTab"
        :tab-names="availableTabs"
      ></Tab-switcher>

      <div class="px-4 bg-light border-start border-end">
        <div v-show="selectedTab === 'Map view'">
          <div class="row pt-2">
            <div class="col">
              <label
                for="mapBaseSelector"
                class="col-form-label col-form-label-sm"
                >Base layer</label
              >
            </div>
            <div class="col">
              <select
                id="mapBaseSelector"
                v-model="mapBaseLayer"
                class="form-select form-select-sm"
              >
                <option v-for="l in availableMapBaseLayers" :value="l.id">
                  {{ l.label }}
                </option>
              </select>
            </div>
            <div class="col">
              <label for="opacity" class="col-form-label col-form-label-sm"
                >Data layer opacity</label
              >
            </div>
            <div class="col">
              <input
                type="range"
                class="custom-range"
                id="opacity"
                min="0"
                max="1"
                step="0.1"
                :value="dataLayerOpacity"
                @input="dataLayerOpacity = $event.target.valueAsNumber"
              />
            </div>
          </div>

          <Observations-Map
            :height="600"
            :initial-zoom="8"
            :initial-lat="50.501"
            :initial-lon="4.4764"
            :tile-server-url-template="
              frontendConfig.apiEndpoints.tileServerUrlTemplate
            "
            :min-max-url="frontendConfig.apiEndpoints.minMaxOccPerHexagonUrl"
            :filters="filters"
            :show-counters="true"
            :base-layer-name="mapBaseLayer"
            :data-layer-opacity="dataLayerOpacity"
            :areas-to-show="filters.areaIds"
            :areas-endpoint-url-template="
              frontendConfig.apiEndpoints.areasUrlTemplate
            "
          ></Observations-Map>
        </div>

        <Observations-Table
          v-show="selectedTab === 'Table view'"
          :filters="filters"
          :observations-json-url="
            frontendConfig.apiEndpoints.observationsJsonUrl
          "
          :observation-page-url-template="
            frontendConfig.apiEndpoints.observationDetailsUrlTemplate
          "
        >
        </Observations-Table>
      </div>
    </div>
  </div>
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
} from "../interfaces";
import axios from "axios";
import ObservationsCounter from "../components/ObservationsCounter.vue";
import TabSwitcher from "../components/TabSwitcher.vue";
import ObservationsTable from "../components/ObservationsTable.vue";
import ObservationsMap from "../components/ObservationsMap.vue";
import ModalMultiSelector from "../components/ModalMultiSelector.vue";
import CustomObservationsTimeLine from "./CustomObservationTimeLine.vue";
import { DateTime } from "luxon";
import { debounce, DebouncedFunc } from "lodash";

declare const ripariasConfig: FrontEndConfig;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  availableDatasets: DatasetInformation[];
  availableAreas: AreaInformation[];
  filters: DashboardFilters;
  mapBaseLayer: string;
  availableMapBaseLayers: SelectionEntry[];
  selectedTab: string;
  availableTabs: string[];
  dataLayerOpacity: number;
  debouncedUpdateDateFilters: null | DebouncedFunc<(range: DateRange) => void>;
}

export default defineComponent({
  name: "IndexPageRootComponent",
  components: {
    CustomObservationsTimeLine,
    ObservationsMap,
    ObservationsCounter,
    TabSwitcher,
    ObservationsTable,
    ModalMultiSelector,
  },
  data: function (): IndexPageRootComponentData {
    return {
      frontendConfig: ripariasConfig,

      availableSpecies: [],
      availableDatasets: [],
      availableAreas: [],

      availableMapBaseLayers: [
        { id: "toner", label: "Stamen Toner" },
        { id: "osmHot", label: "OSM HOT" },
        { id: "esriImagery", label: "ESRI World Imagery" },
      ],
      mapBaseLayer: "osmHot",
      selectedTab: "Map view",
      availableTabs: ["Map view", "Table view"],
      filters: {
        speciesIds: [],
        datasetsIds: [],
        areaIds: [],
        startDate: null,
        endDate: null,
        status: null,
      },
      dataLayerOpacity: 0.8,
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
      this.filters.startDate = this.dateTimeToFilterParam(range.start);
      this.filters.endDate = this.dateTimeToFilterParam(range.end);
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

    dateTimeToFilterParam(dt: DateTime | null): string | null {
      if (dt == null) {
        return null;
      } else {
        return dt.toISODate();
      }
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
