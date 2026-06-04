type Trilingual = {
    vernacularNameEn: string;
    vernacularNameNl: string;
    vernacularNameFr: string;
};

// Pick the vernacular name for the active locale. Returns "" when that locale's
// column is empty; SpeciesName.vue falls back to the scientific name on empty.
export function pickVernacular(item: Trilingual, locale: string): string {
    const code = locale.slice(0, 2);
    if (code === "nl") return item.vernacularNameNl;
    if (code === "fr") return item.vernacularNameFr;
    return item.vernacularNameEn;
}
