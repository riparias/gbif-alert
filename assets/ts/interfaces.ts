// To use with <select>, checkboxes, ...
import TileLayer from "ol/layer/Tile";
import Stamen from "ol/source/Stamen";
import OSM from "ol/source/OSM";
import {XYZ} from "ol/source";
import {DateTime} from "luxon";

export interface SelectionEntry {
  id: string | number;
  label: string;
}

export interface Tab {
  name: string;
  id: string;
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

// Data comes directly from the backend, keep in sync with Species.as_dict()
export interface SpeciesInformation {
  id: number;
  scientificName: string;
  vernacularName: string;
  gbifTaxonKey: number;
  tags: string[];
}

// Extends SpeciesInformation with a label property. Since it has all properties of SelectionEntry, it can be used as a SelectionEntry
export interface SpeciesInformationWithLabel extends SpeciesInformation {
    label: string;
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
  alertPageUrlTemplate: string;
}

export interface MapConfig {
  initialZoom: number;
  initialLat: number;
  initialLon: number;
}

// Keep in sync with templatetags.pterois_extras.js_config_object
export interface FrontEndConfig {
  ripariasAreaGeojsonUrl: string;
  apiEndpoints: EndpointsUrls;
  authenticatedUser: boolean;
  userId?: number; // Only set if authenticatedUser is true
  mainMapConfig: MapConfig;
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
