import { ref } from "vue";
import { defineStore } from "pinia";
import { getNavConfig, type SpeciesNameMode } from "../utils/navConfig";

const COOKIE_NAME = "gbif-alert.species-name-display";
const DEFAULT_MODE: SpeciesNameMode = "scientific";
const ONE_YEAR_SECONDS = 365 * 24 * 60 * 60;

function isValidMode(value: unknown): value is SpeciesNameMode {
    return value === "scientific" || value === "vernacular";
}

function readInitialMode(): SpeciesNameMode {
    const fromConfig = getNavConfig().speciesNameMode;
    return isValidMode(fromConfig) ? fromConfig : DEFAULT_MODE;
}

function writeCookie(mode: SpeciesNameMode): void {
    document.cookie =
        `${COOKIE_NAME}=${mode}; ` +
        `Path=/; Max-Age=${ONE_YEAR_SECONDS}; SameSite=Lax`;
}

export const usePreferencesStore = defineStore("preferences", () => {
    const speciesNameMode = ref<SpeciesNameMode>(readInitialMode());

    function setSpeciesNameMode(mode: SpeciesNameMode) {
        if (!isValidMode(mode)) return;
        speciesNameMode.value = mode;
        writeCookie(mode);
    }

    function toggleSpeciesNameMode() {
        setSpeciesNameMode(
            speciesNameMode.value === "scientific" ? "vernacular" : "scientific",
        );
    }

    return { speciesNameMode, setSpeciesNameMode, toggleSpeciesNameMode };
});
