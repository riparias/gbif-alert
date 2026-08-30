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

const shades = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"];

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

// Django templates that render their own page content (the password reset flow)
// share base.html with the SPA shell, and mark the mount point accordingly.
// Their URLs are not SPA routes, so without this the router's catch-all would
// draw NotFoundPage above the server-rendered content. Registering the current
// path as a contentless route keeps the navbar and footer chrome, and leaves
// navigation away from the page working normally.
if (document.getElementById("frontend")?.dataset.serverRendered === "true") {
    const serverRenderedPath = window.location.pathname;
    router.addRoute({ path: serverRenderedPath, component: { render: () => null } });
    // That content sits outside the Vue app, so the router cannot replace it.
    // Drop it once the user navigates client-side to a real SPA route,
    // otherwise it lingers below the page they asked for.
    router.afterEach((to) => {
        if (to.path !== serverRenderedPath) {
            document.getElementById("server-rendered-content")?.remove();
        }
    });
}

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
