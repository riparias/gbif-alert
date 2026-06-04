import { ref } from "vue";
import { defineStore } from "pinia";
import type { components } from "../types/api";

type SpeciesOut = components["schemas"]["SpeciesOut"];
type DatasetOut = components["schemas"]["DatasetOut"];
type AreaOut = components["schemas"]["AreaOut"];
type BasisOfRecordOut = components["schemas"]["BasisOfRecordOut"];
type AlertNotificationFrequencyOut =
    components["schemas"]["AlertNotificationFrequencyOut"];

// Cache of lookup lists so components can resolve IDs (and enum codes) to
// human-readable names without duplicate requests. Populated by FilterSidebar
// (index page) and, for the alert pages, by useDisplayLabels.ensureAlertLabelsLoaded().
export const useFilterOptionsStore = defineStore("filterOptions", () => {
    const species = ref<SpeciesOut[]>([]);
    const datasets = ref<DatasetOut[]>([]);
    const areas = ref<AreaOut[]>([]);
    const basisOfRecord = ref<BasisOfRecordOut[]>([]);
    const frequencies = ref<AlertNotificationFrequencyOut[]>([]);

    return { species, datasets, areas, basisOfRecord, frequencies };
});
