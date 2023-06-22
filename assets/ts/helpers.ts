import {DashboardFilters} from "./interfaces";
import {DateTime} from "luxon";
import {hsl} from "d3-color";

const qs = require("qs");

export function filtersToQuerystring(filters: DashboardFilters): string {
  return qs.stringify(filters, { arrayFormat: "brackets" });
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

export function legibleColor (color: string): string {
  return hsl(color).l > 0.5 ? "#000" : "#fff";
}

export function scientificNameFormatter(value: string): string {
  return `<i>${value}</i>`;
}

export function gbifTaxonKeyFormatter(value: string): string {
  return `<a href="https://www.gbif.org/species/${value}" target="_blank">${value}</a>`;
}