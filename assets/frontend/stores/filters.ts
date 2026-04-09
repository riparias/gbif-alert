import { ref } from "vue";
import { defineStore } from "pinia";

export const useFiltersStore = defineStore("filters", () => {
    const speciesIds = ref<number[]>([]);
    const datasetsIds = ref<number[]>([]);
    const basisOfRecordIds = ref<number[]>([]);
    const areaIds = ref<number[]>([]);
    const initialDataImportIds = ref<number[]>([]);

    const startDate = ref<string | null>(null);
    const endDate = ref<string | null>(null);

    const status = ref<"seen" | "unseen" | null>(null);
    const verifiedFilter = ref<"all" | "verified" | "unverified">("all");

    const areaFilterMode = ref<"inside" | "approaching" | "both">("inside");
    const approachingDistanceKm = ref<number | null>(null);

    function $reset() {
        speciesIds.value = [];
        datasetsIds.value = [];
        basisOfRecordIds.value = [];
        areaIds.value = [];
        initialDataImportIds.value = [];
        startDate.value = null;
        endDate.value = null;
        status.value = null;
        verifiedFilter.value = "all";
        areaFilterMode.value = "inside";
        approachingDistanceKm.value = null;
    }

    return {
        speciesIds,
        datasetsIds,
        basisOfRecordIds,
        areaIds,
        initialDataImportIds,
        startDate,
        endDate,
        status,
        verifiedFilter,
        areaFilterMode,
        approachingDistanceKm,
        $reset,
    };
});
