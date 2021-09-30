import { createApp } from "vue";
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

interface RootAppData {
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

const app = createApp({
  components: {
    OccurrencesMap,
    OccurrencesCounter,
    TabSwitcher,
    OccurrencesTable,
    ModalMultiSelector,
  },
  delimiters: ["[[", "]]"],
  data: function (): RootAppData {
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

app.mount("#app");
