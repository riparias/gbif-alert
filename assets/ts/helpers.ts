import { DashboardFilters } from "./interfaces";
const qs = require("qs");

export function filtersToQuerystring(filters: DashboardFilters): string {
  return qs.stringify(filters, { arrayFormat: "brackets" });
}
