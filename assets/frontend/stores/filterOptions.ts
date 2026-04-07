import { ref } from "vue";
import { defineStore } from "pinia";
import type { components } from "../types/api";

type SpeciesOut = components["schemas"]["SpeciesOut"];
type DatasetOut = components["schemas"]["DatasetOut"];
type AreaOut = components["schemas"]["AreaOut"];
type BasisOfRecordOut = components["schemas"]["BasisOfRecordOut"];

// Holds the option lists loaded by FilterSidebar so that sibling components
// (e.g. ActiveFilterChips) can resolve IDs to human-readable names without
// making duplicate API requests.
export const useFilterOptionsStore = defineStore("filterOptions", () => {
    const species = ref<SpeciesOut[]>([]);
    const datasets = ref<DatasetOut[]>([]);
    const areas = ref<AreaOut[]>([]);
    const basisOfRecord = ref<BasisOfRecordOut[]>([]);

    return { species, datasets, areas, basisOfRecord };
});
