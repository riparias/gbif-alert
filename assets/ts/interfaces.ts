// To use with <select>, checkboxes, ...
import TileLayer from "ol/layer/Tile";
import Stamen from "ol/source/Stamen";
import OSM from "ol/source/OSM";
import { XYZ } from "ol/source";

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
}

export interface SpeciesInformation {
  id: number;
  scientificName: string;
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

interface EndpointsUrls {
  speciesListUrl: string;
  datasetsListUrl: string;
  areasListUrl: string;
  tileServerUrlTemplate: string;
  areasUrlTemplate: string;
  observationsCounterUrl: string;
  observationsJsonUrl: string;
  observationsHistogramDataUrl: string;
  observationDetailsUrlTemplate: string;
}

// Keep in sync with templatetags.riparias_extras.js_config_object
export interface FrontEndConfig {
  currentLanguageCode: string;
  targetCountryCode: string;
  ripariasAreaGeojsonUrl: string;
  apiEndpoints: EndpointsUrls;
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
  viewedByCurrentUser?: boolean;
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
