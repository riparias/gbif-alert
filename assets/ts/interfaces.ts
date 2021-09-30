// To use with <select>, checkboxes, ...
export interface SelectionEntry {
  id: string | number;
  label: string;
}

export interface DashboardFilters {
  speciesIds: Number[];
  startDate: string | null;
  endDate: string | null;
}

export interface SpeciesInformation {
  id: Number;
  scientificName: String;
  gbifTaxonKey: Number;
  groupCode: String;
  categoryCode: String;
}

interface EndpointsUrls {
  speciesListUrl: string;
  tileServerUrlTemplate: string;
  occurrencesCounterUrl: string;
  occurrencesJsonUrl: string;
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
}
