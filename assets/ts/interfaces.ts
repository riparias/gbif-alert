// To use with <select>, checkboxes, ...
import TileLayer from "ol/layer/Tile";
import Stamen from "ol/source/Stamen";
import OSM from "ol/source/OSM";
import { XYZ } from "ol/source";
import { DateTime } from "luxon";
import { Feature } from "ol";
import RenderFeature from "ol/render/Feature";
import { Style } from "ol/style";

export interface SelectionEntry {
  id: string | number;
  label: string;
}

export interface DashboardFilters {
  speciesIds: Number[];
  datasetsIds: Number[];
  startDate: string | null;
  endDate: string | null;
  areaIds: Number[];
  status: "seen" | "unseen" | null;
  initialDataImportIds: Number[];
}

export interface SpeciesInformation {
  id: number;
  scientificName: string;
  vernacularName: string;
  gbifTaxonKey: number;
  groupCode: string;
  categoryCode: string;
}

export interface DatasetInformation {
  id: number;
  gbifKey: number;
  name: string;
}

export interface AreaInformation {
  id: number;
  name: string;
  isUserSpecific: boolean;
}

export interface DataImportInformation {
  id: number;
  str: string;
  startTimestamp: string; // Format: "2022-01-21T11:31:35.490Z"
}

export interface EndpointsUrls {
  speciesListUrl: string;
  datasetsListUrl: string;
  areasListUrl: string;
  dataImportsListUrl: string;
  tileServerAggregatedUrlTemplate: string; // On this URL, observations are aggregated per hexagon
  tileServerUrlTemplate: string; // On this URL, observations are *not* aggregated
  areasUrlTemplate: string;
  observationsCounterUrl: string;
  observationsJsonUrl: string;
  observationsHistogramDataUrl: string;
  observationDetailsUrlTemplate: string;
  markObservationsAsSeenUrl: string;
  minMaxOccPerHexagonUrl: string;
  alertAsFiltersUrl: string;
}

// Keep in sync with templatetags.riparias_extras.js_config_object
export interface FrontEndConfig {
  ripariasAreaGeojsonUrl: string;
  apiEndpoints: EndpointsUrls;
  authenticatedUser: boolean;
  userId?: number; // Only set if authenticatedUser is true
}

// Keep in sync with Models.Observation.as_dict()
export interface JsonObservation {
  id: number;
  stableId: string;
  gbifId: number;
  lat: number;
  lon: number;
  date: string;
  speciesName: string;
  datasetName: string;
  seenByCurrentUser?: boolean;
}

export interface PreparedHistogramDataEntry {
  // Derived from HistogramDataEntry, the year and month are aggregated to a string for the bar chart
  yearMonth: string;
  count: number;
}

export interface BaseLayerEntry {
  name: string;
  layer: TileLayer<Stamen> | TileLayer<OSM> | TileLayer<XYZ>;
}

export interface DateRange {
  start: DateTime | null;
  end: DateTime | null;
}
