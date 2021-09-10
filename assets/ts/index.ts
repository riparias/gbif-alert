import Vue from "vue";
import OccurrencesMap from "./components/OccurrencesMap.vue";
import {DashboardFilters, SpeciesInformation, FrontEndConfig, OptionForSelect} from "./interfaces";
import SpeciesSelector from "./components/SpeciesSelector.vue";
import axios from "axios";
import OccurrencesCounter from "./components/OccurrencesCounter.vue";

declare const ripariasConfig: FrontEndConfig;

interface RootAppData {
    frontendConfig: FrontEndConfig
    availableSpecies: SpeciesInformation[]
    filters: DashboardFilters,
    mapBaseLayer: string
    availableMapBaseLayers: OptionForSelect[]
}

new Vue({
    el: "#app",
    components: {
        OccurrencesMap, SpeciesSelector, OccurrencesCounter
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
            mapBaseLayer: 'toner',
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
