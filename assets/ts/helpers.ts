import {AreaInformation, DashboardFilters, DataRow, SpeciesInformation} from "./interfaces";
import {DateTime} from "luxon";
import {hsl} from "d3-color";

const qs = require("qs");

export function filtersToQuerystring(filters: DashboardFilters): string {
    return qs.stringify(filters, {arrayFormat: "brackets"});
}

export function dateTimeToFilterParam(dt: DateTime | null): string | null {
    if (dt == null) {
        return null;
    } else {
        return dt.toISODate();
    }
}

export function formatCount(val: number): string {
    return new Intl.NumberFormat().format(val);
}

export function wordToColor(word: string): string {
    let hash = 0;
    for (let i = 0; i < word.length; i++) {
        hash = word.charCodeAt(i) + ((hash << 5) - hash);
    }
    let color = "#";
    for (let i = 0; i < 3; i++) {
        const value = (hash >> (i * 8)) & 0xff;
        color += ("00" + value.toString(16)).substr(-2);
    }
    return color;
}

export function legibleColor(color: string): string {
    return hsl(color).l > 0.5 ? "#000" : "#fff";
}

export function scientificNameFormatter(rawValue: string, highlightedValue: string): string {
    return `<i>${highlightedValue}</i>`;
}

export function gbifTaxonKeyFormatter(rawValue: string, highlightedValue: string): string {
    return `<a href="https://www.gbif.org/species/${rawValue}" target="_blank">${highlightedValue}</a>`;
}

export function prepareAreasData(areasData: AreaInformation[], translationFunction: (s: string) => string): DataRow[] {
    // Input: areas data, as returned from the server
    // Output: datarows suitable for the <selector> component
    return areasData.map((a: AreaInformation) => {
        return {
            id: a.id,
            columnData: [a.name, (a.isUserSpecific ? translationFunction('message.userSpecific') : translationFunction('message.shared'))],
            tags: a.tags,
        };
    });
}

export function prepareSpeciesData(speciesData: SpeciesInformation[]): DataRow[] {
    // Input: spcies data, as returned from the server
    // Output: datarows suitable for the <selector> component
    return speciesData.map((s) => {
        return {id: s.id, columnData: [s.scientificName, s.vernacularName, s.gbifTaxonKey], tags: s.tags};
    });
}