<template>
  <div class="col-3 bg-light">
    <h4 class="my-3">Data filtering</h4>
    <Modal-Multi-Selector
      button-label="species"
      modal-title="Species to include"
      :entries="availableSpeciesAsEntries"
      @entries-changed="changeSelectedSpecies"
    ></Modal-Multi-Selector>

    <p>
      <label for="mapBaseSelector" class="form-label">Source dataset</label>
    </p>
    <p><label for="mapBaseSelector" class="form-label">Date range</label></p>

    <h4 class="my-3">Map style</h4>

    <label for="mapBaseSelector" class="form-label">Base layer</label>
    <select
      id="mapBaseSelector"
      v-model="mapBaseLayer"
      class="form-select form-select-sm"
    >
      <option v-for="l in availableMapBaseLayers" :value="l.id">
        {{ l.label }}
      </option>
    </select>

    <div class="form-group row">
      <label class="col-sm-6 col-form-label col-form-label-sm" for="opacity"
        >Data layer opacity</label
      >
      <input
        type="range"
        class="col-sm-5 custom-range"
        id="opacity"
        min="0"
        max="1"
        step="0.1"
        v-model.number="dataLayerOpacity"
      />
    </div>

    <div class="form-check form-switch">
      <input
        v-model="showRipariasArea"
        class="form-check-input"
        type="checkbox"
        id="ripariasAreaCheckbox"
      />
      <label class="form-check-label" for="ripariasAreaCheckbox"
        >Show LIFE RIPARIAS study area</label
      >
    </div>
  </div>

  <div class="col-9 overflow-auto">
    <h4 class="my-3">Results</h4>
    <Occurrences-counter
      :counter-url="frontendConfig.apiEndpoints.occurrencesCounterUrl"
      :filters="filters"
    ></Occurrences-counter>

    <Tab-switcher
      class="my-3"
      v-model="selectedTab"
      :tab-names="availableTabs"
    ></Tab-switcher>

    <Occurrences-Map
      v-show="selectedTab === 'Map view'"
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
      :riparias-geojson-url="frontendConfig.ripariasAreaGeojsonUrl"
      :show-riparias-area="showRipariasArea"
      :data-layer-opacity="dataLayerOpacity"
    ></Occurrences-Map>

    <Occurrences-Table
      v-show="selectedTab === 'Table view'"
      :filters="filters"
      :occurrences-json-url="frontendConfig.apiEndpoints.occurrencesJsonUrl"
      :occurrence-page-url-template="
        frontendConfig.apiEndpoints.occurrenceDetailsUrlTemplate
      "
    >
    </Occurrences-Table>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import {
  DashboardFilters,
  SpeciesInformation,
  FrontEndConfig,
  SelectionEntry,
} from "../interfaces";
import axios from "axios";
import OccurrencesCounter from "../components/OccurrencesCounter.vue";
import TabSwitcher from "../components/TabSwitcher.vue";
import OccurrencesTable from "../components/OccurrencesTable.vue";
import OccurrencesMap from "../components/OccurrencesMap.vue";
import ModalMultiSelector from "../components/ModalMultiSelector.vue";

declare const ripariasConfig: FrontEndConfig;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  filters: DashboardFilters;
  mapBaseLayer: string;
  availableMapBaseLayers: SelectionEntry[];
  selectedTab: string;
  availableTabs: string[];
  showRipariasArea: boolean;
  dataLayerOpacity: number;
}

export default defineComponent({
  name: "IndexPageRootComponent",
  components: {
    OccurrencesMap,
    OccurrencesCounter,
    TabSwitcher,
    OccurrencesTable,
    ModalMultiSelector,
  },
  data: function (): IndexPageRootComponentData {
    return {
      frontendConfig: ripariasConfig,

      availableSpecies: [],
      availableMapBaseLayers: [
        { id: "toner", label: "Stamen Toner" },
        { id: "osmHot", label: "OSM HOT" },
      ],
      mapBaseLayer: "osmHot",
      showRipariasArea: true,
      selectedTab: "Map view",
      availableTabs: ["Map view", "Table view"],
      filters: {
        speciesIds: [],
        startDate: null,
        endDate: null,
      },
      dataLayerOpacity: 0.8,
    };
  },
  computed: {
    availableSpeciesAsEntries: function (): SelectionEntry[] {
      return this.availableSpecies.map((s: SpeciesInformation) => {
        return { id: s.id, label: s.scientificName };
      });
    },
  },
  methods: {
    changeSelectedSpecies: function (speciesIds: Number[]) {
      this.filters.speciesIds = speciesIds;
    },

    populateAvailableSpecies: function () {
      axios
        .get(this.frontendConfig.apiEndpoints.speciesListUrl)
        .then((response) => {
          this.availableSpecies = response.data;
        });
    },
  },

  mounted: function () {
    this.populateAvailableSpecies();
  },
});
</script>
