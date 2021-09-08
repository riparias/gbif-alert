import Vue from "vue";
import OccurrencesMap from "./components/OccurrencesMap.vue";
import {DashboardFilters, SpeciesInformation, FrontEndConfig} from "./interfaces";
import SpeciesSelector from "./components/SpeciesSelector.vue";
import axios from "axios";

declare const ripariasConfig: FrontEndConfig;

interface RootAppData {
    frontendConfig: FrontEndConfig
    availableSpecies: SpeciesInformation[]
    filters: DashboardFilters
}

new Vue({
    el: "#app",
    components: {
        OccurrencesMap, SpeciesSelector
    },
    delimiters: ["[[", "]]"],
    data: function (): RootAppData {
        return {
            frontendConfig: ripariasConfig,
            availableSpecies: [],
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
