import type { useFiltersStore } from "../stores/filters";

type FiltersStore = ReturnType<typeof useFiltersStore>;

/**
 * Serialize the current filters store into URLSearchParams suitable for the
 * api/v2 observation endpoints (list, histogram, mark-as-seen).
 *
 * Callers add their own extras (page, pageSize, orderBy, etc.) onto the
 * returned object.
 *
 * Note: the legacy tile-server endpoints expect `speciesIds[]` bracket
 * notation - they have their own serializer in ObservationsMap.vue.
 */
export function filtersToParams(
    filtersStore: FiltersStore,
    { includeDateRange = true }: { includeDateRange?: boolean } = {}
): URLSearchParams {
    const params = new URLSearchParams();
    for (const id of filtersStore.speciesIds) params.append("speciesIds", String(id));
    for (const id of filtersStore.datasetsIds) params.append("datasetsIds", String(id));
    for (const id of filtersStore.areaIds) params.append("areaIds", String(id));
    for (const id of filtersStore.basisOfRecordIds)
        params.append("basisOfRecordIds", String(id));
    for (const id of filtersStore.initialDataImportIds)
        params.append("initialDataImportIds", String(id));
    if (includeDateRange) {
        if (filtersStore.startDate) params.set("startDate", filtersStore.startDate);
        if (filtersStore.endDate) params.set("endDate", filtersStore.endDate);
    }
    if (filtersStore.status) params.set("status", filtersStore.status);
    params.set("verifiedFilter", filtersStore.verifiedFilter);
    params.set("areaFilterMode", filtersStore.areaFilterMode);
    if (filtersStore.approachingDistanceKm !== null) {
        params.set(
            "approachingDistanceKm",
            String(filtersStore.approachingDistanceKm)
        );
    }
    return params;
}
