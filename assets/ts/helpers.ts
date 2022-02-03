import { DashboardFilters } from "./interfaces";
import { DateTime } from "luxon";
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
