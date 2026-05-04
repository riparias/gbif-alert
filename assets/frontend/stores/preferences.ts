import { defineStore } from "pinia";
import { getNavConfig, type SpeciesNameMode } from "../utils/navConfig";

const COOKIE_NAME = "gbif-alert.species-name-display";
const VALID_MODES: ReadonlyArray<SpeciesNameMode> = ["scientific", "vernacular"];
const DEFAULT_MODE: SpeciesNameMode = "scientific";
const ONE_YEAR_SECONDS = 365 * 24 * 60 * 60;

function isValidMode(value: unknown): value is SpeciesNameMode {
    return typeof value === "string" && (VALID_MODES as readonly string[]).includes(value);
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

export const usePreferencesStore = defineStore("preferences", {
    state: (): { speciesNameMode: SpeciesNameMode } => ({
        speciesNameMode: readInitialMode(),
    }),
    actions: {
        setSpeciesNameMode(mode: SpeciesNameMode) {
            if (!isValidMode(mode)) return;
            this.speciesNameMode = mode;
            writeCookie(mode);
        },
        toggleSpeciesNameMode() {
            this.setSpeciesNameMode(
                this.speciesNameMode === "scientific" ? "vernacular" : "scientific",
            );
        },
    },
});
