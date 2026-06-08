import type { useFiltersStore } from "../stores/filters";
import type { components } from "../types/api";

type FiltersStore = ReturnType<typeof useFiltersStore>;
type FiltersQuery = components["schemas"]["FiltersQuery"];

/**
 * Serialize the current filters store into URLSearchParams suitable for the
 * api/v2 observation endpoints (list, histogram, mark-as-viewed).
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
    for (const id of filtersStore.datasetIds) params.append("datasetIds", String(id));
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

/**
 * Serialize the filters store into a FiltersQuery JSON body, for the mutating
 * POST endpoints that take their filters in the request body (e.g. bulk
 * mark-as-viewed - audit N4).
 */
export function filtersToBody(filtersStore: FiltersStore): FiltersQuery {
    return {
        speciesIds: filtersStore.speciesIds,
        datasetIds: filtersStore.datasetIds,
        basisOfRecordIds: filtersStore.basisOfRecordIds,
        areaIds: filtersStore.areaIds,
        initialDataImportIds: filtersStore.initialDataImportIds,
        startDate: filtersStore.startDate,
        endDate: filtersStore.endDate,
        status: filtersStore.status,
        verifiedFilter: filtersStore.verifiedFilter,
        areaFilterMode: filtersStore.areaFilterMode,
        approachingDistanceKm: filtersStore.approachingDistanceKm,
    };
}
