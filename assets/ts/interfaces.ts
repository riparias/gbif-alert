// To use with <select>, checkboxes, ...
export interface SelectionEntry {
  id: string | number;
  label: string;
}

export interface DashboardFilters {
  speciesIds: Number[];
  datasetsIds: Number[];
  startDate: string | null;
  endDate: string | null;
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

interface EndpointsUrls {
  speciesListUrl: string;
  datasetsListUrl: string;
  tileServerUrlTemplate: string;
  occurrencesCounterUrl: string;
  occurrencesJsonUrl: string;
  occurrencesHistogramDataUrl: string;
}

// Keep in sync with templatetags.riparias_extras.js_config_object
export interface FrontEndConfig {
  currentLanguageCode: string;
  targetCountryCode: string;
  ripariasAreaGeojsonUrl: string;
  apiEndpoints: EndpointsUrls;
}

// Keep in sync with Models.Occurrence.as_dict()
export interface JsonOccurrence {
  id: number;
  gbifId: number;
  lat: number;
  lon: number;
  date: string;
  speciesName: string;
  datasetName: string;
}

export interface PreparedHistogramDataEntry {
  // Derived from HistogramDataEntry, the year and month are aggregated to a string for the bar chart
  yearMonth: string;
  count: number;
}
