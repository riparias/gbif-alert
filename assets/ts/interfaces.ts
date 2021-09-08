export interface DashboardFilters {
  speciesId: Number | null
  startDate: string | null
  endDate: string | null
}

export interface SpeciesInformation {
  id: Number
  scientificName: String
  gbifTaxonKey: Number
  groupCode: String
  categoryCode: String
}

interface EndpointsUrls {
  speciesListUrl: string
  tileServerUrlTemplate: string
}

// Keep this interface in sync with templatetags.riparias_extras.js_config_object
export interface FrontEndConfig {
  currentLanguageCode: String
  targetCountryCode: String
  apiEndpoints: EndpointsUrls
}