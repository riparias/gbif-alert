// Typed wrapper around the nav-config JSON block Django injects into every page.
// Parse is done once and cached; call getNavConfig() from any component instead of
// repeating JSON.parse(document.getElementById("gbif-alert-nav-config")...) inline.

export interface Language {
    code: string;
    nameLocal: string;
}

export interface NavUser {
    isAuthenticated: boolean;
    username: string | null;
    isSuperuser: boolean;
    hasUnseenNews: boolean;
    hasAlertsWithUnseenObservations: boolean;
}

interface NavUrls {
    index: string;
    news: string;
    myAlerts: string;
    aboutSite: string;
    aboutData: string;
    profile: string;
    passwordChange: string;
    myCustomAreas: string;
    signout: string;
    signin: string;
    signup: string;
    admin: string;
    setLanguage: string;
}

interface MapConfig {
    initialPosition: { initialZoom: number; initialLat: number; initialLon: number };
    zoomLevelMinMaxQuery: number;
    tileServerUrlTemplate: string;
    tileServerAggregatedUrlTemplate: string;
    areasUrlTemplate: string;
    minMaxOccPerHexagonUrl: string;
    observationDetailsUrlTemplate: string;
}

export interface NavConfig {
    siteName: string;
    primaryPalette: string;
    currentLanguage: string;
    enabledLanguages: Language[];
    user: NavUser;
    urls: NavUrls;
    map: MapConfig;
}

let _cache: NavConfig | null = null;

export function getNavConfig(): NavConfig {
    if (!_cache) {
        const el = document.getElementById("gbif-alert-nav-config");
        _cache = el ? JSON.parse(el.textContent!) : ({} as NavConfig);
    }
    return <NavConfig>_cache;
}
