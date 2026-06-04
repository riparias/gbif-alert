import { useFilterOptionsStore } from "../stores/filterOptions";

// Resolves option ids (currently basis-of-record) to their human-readable names
// for the observation table and detail drawer. The backend now returns ids
// instead of pre-formatted labels (audit N7), so the SPA does the join.
//
// ObservationsView renders on the alert detail page too, which has no
// FilterSidebar to populate the option lists, so the list is loaded lazily.
// PR6b extends this composable with datasets/areas/frequencies for the alert pages.
export function useDisplayLabels() {
    const store = useFilterOptionsStore();

    async function ensureBasisOfRecordLoaded(): Promise<void> {
        if (store.basisOfRecord.length) return;
        const res = await fetch("/api/v2/basis-of-record/");
        if (res.ok) store.basisOfRecord = await res.json();
    }

    function basisOfRecordName(id: number): string {
        return store.basisOfRecord.find((b) => b.id === id)?.name ?? "";
    }

    return { ensureBasisOfRecordLoaded, basisOfRecordName };
}
