// Pick the vernacular name for the active locale. Returns "" when that locale's
// name is empty; SpeciesName.vue falls back to the scientific name on empty.
export function pickVernacular(
    item: { vernacularNames: Record<string, string> },
    locale: string,
): string {
    return item.vernacularNames[locale.slice(0, 2)] ?? "";
}
