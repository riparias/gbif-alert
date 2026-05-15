import "primeicons/primeicons.css";
import "./styles/badges.css";
import "./styles/layout.css";
import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import PrimeVue from "primevue/config";
import Material from "@primeuix/themes/material";
import { definePreset } from "@primeuix/themes";
import { createI18n } from "vue-i18n";
import ConfirmationService from "primevue/confirmationservice";
import ToastService from "primevue/toastservice";

import { messages } from "./translations";
import { getNavConfig } from "./utils/navConfig";

import App from "./App.vue";
import { routes } from "./router/index";

// --- PrimeVue theme ---
// Read the primary palette name from the nav config Django injects into every page
// (via the nav_config_json template tag). This lets each deployment choose its own
// branding color via GBIF_ALERT["PRIMEVUE_PRIMARY_PALETTE"] in Django settings.
const primaryPalette: string = getNavConfig().primaryPalette;

const shades = [
    "50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950",
];

const GbifAlertPreset = definePreset(Material, {
    semantic: {
        // Map all primary tokens to the chosen palette so every PrimeVue component
        // (buttons, focus rings, active states, ...) uses the deployment's color.
        primary: Object.fromEntries(shades.map((s) => [s, `{${primaryPalette}.${s}}`])),
    },
    components: {
        // Override Menubar tokens so the navbar background matches the primary color
        // with properly derived hover/active/focus states - no :deep() CSS hacks needed.
        menubar: {
            root: {
                background: "{primary.500}",
                color: "#ffffff",
            },
            item: {
                color: "#ffffff",
                focusBackground: "{primary.400}",
                focusColor: "#ffffff",
                activeBackground: "{primary.600}",
                activeColor: "#ffffff",
            },
        },
    },
});

// --- App setup ---

const pinia = createPinia();

const router = createRouter({
    history: createWebHistory(),
    routes,
});

const i18n = createI18n({
    locale: (window as any).LANGUAGE_CODE,
    fallbackLocale: "en",
    legacy: false,
    messages,
});

const app = createApp(App);
app.use(pinia);
app.use(router);
app.use(PrimeVue, { theme: { preset: GbifAlertPreset } });
app.use(i18n);
app.use(ConfirmationService);
app.use(ToastService);
app.mount("#frontend");
