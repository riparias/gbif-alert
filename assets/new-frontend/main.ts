import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import PrimeVue from "primevue/config";
import Aura from "@primeuix/themes/aura";
import { createI18n } from "vue-i18n";

// Temporary cross-reference: translations live in the old frontend until Phase 6
// removes assets/ts/ entirely.
import { messages } from "../ts/translations";

import App from "./App.vue";
import { routes } from "./router/index";

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
app.use(PrimeVue, { theme: { preset: Aura } });
app.use(i18n);
app.mount("#new-frontend");
