<template>
  <div class="row">
    <div class="col-sm my-2">
      <div class="row">
        <div class="col-2">
          <b>Data filtering:</b>
        </div>

        <div class="col-7">
          <Modal-Multi-Selector
            button-label="species"
            modal-title="Species to include"
            :entries="availableSpeciesAsEntries"
            @entries-changed="changeSelectedSpecies"
          ></Modal-Multi-Selector>
        </div>

        <div class="col-3">
          <Occurrences-counter
            class="float-right"
            :counter-url="frontendConfig.apiEndpoints.occurrencesCounterUrl"
            :filters="filters"
          ></Occurrences-counter>
        </div>
      </div>
    </div>
  </div>

  <div class="row">
    <div class="col">
      <Occurrences-time-line
        :filters="filters"
        :histogram-data-url="
          frontendConfig.apiEndpoints.occurrencesHistogramDataUrl
        "
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
            <div class="col form-switch">
              <input
                v-model="showRipariasArea"
                class="form-check-input"
                type="checkbox"
                id="ripariasAreaCheckbox"
              />

              <label
                class="col-form-label col-form-label-sm form-check-label"
                for="ripariasAreaCheckbox"
                >Show LIFE RIPARIAS study area</label
              >
            </div>
          </div>

          <Occurrences-Map
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
        </div>

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
    </div>
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
import OccurrencesTimeLine from "./OccurrencesTimeLine.vue";

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
    OccurrencesTimeLine,
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
