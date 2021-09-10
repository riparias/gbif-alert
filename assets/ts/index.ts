import Vue from "vue";
import OccurrencesMap from "./components/OccurrencesMap.vue";
import {DashboardFilters, SpeciesInformation, FrontEndConfig, OptionForSelect} from "./interfaces";
import SpeciesSelector from "./components/SpeciesSelector.vue";
import axios from "axios";
import OccurrencesCounter from "./components/OccurrencesCounter.vue";
import TabSwitcher from "./components/TabSwitcher.vue";
import OccurrencesTable from "./components/OccurrencesTable.vue";

declare const ripariasConfig: FrontEndConfig;

interface RootAppData {
    frontendConfig: FrontEndConfig
    availableSpecies: SpeciesInformation[]
    filters: DashboardFilters,
    mapBaseLayer: string
    availableMapBaseLayers: OptionForSelect[]
    selectedTab: string
    availableTabs: string[]
}

new Vue({
    el: "#app",
    components: {
        OccurrencesMap, SpeciesSelector, OccurrencesCounter, TabSwitcher, OccurrencesTable
    },
    delimiters: ["[[", "]]"],
    data: function (): RootAppData {
        return {
            frontendConfig: ripariasConfig,

            availableSpecies: [],
            availableMapBaseLayers: [
                { value: 'toner', label: 'Stamen Toner' },
                { value: 'osmHot', label: 'OSM HOT' },
            ],
            mapBaseLayer: 'osmHot',
            selectedTab: 'Map view',
            availableTabs: ['Map view', 'Table view'],
            filters: {
                speciesId: null,
                startDate: null,
                endDate: null
            }
        }
    },

    methods: {
        changeSelectedSpecies: function (speciesId: Number) {
            this.filters.speciesId = speciesId;
        },

        populateAvailableSpecies: function () {
            axios.get(this.frontendConfig.apiEndpoints.speciesListUrl
            ).then(response => {
                this.availableSpecies = response.data
            })
        }
    },

    mounted: function () {
        this.populateAvailableSpecies()
    }
});
