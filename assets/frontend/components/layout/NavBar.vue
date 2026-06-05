<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import Menubar from "primevue/menubar";
import Button from "primevue/button";
import Select from "primevue/select";
import Menu from "primevue/menu";
import ToggleSwitch from "primevue/toggleswitch";
import type { MenuItem } from "primevue/menuitem";
import { storeToRefs } from "pinia";
import { getNavConfig } from "../../utils/navConfig";
import { getCsrf } from "../../utils/csrf";
import { usePreferencesStore } from "../../stores/preferences";

// Custom nav item: extends MenuItem with our badge-dot flag.
// PrimeVue's MenuItem type has an open index signature, so extra fields are allowed.
interface NavItem extends MenuItem {
    showDot?: boolean;
}

// --- Config ---

const config = getNavConfig();
const route = useRoute();
const { t } = useI18n();

const preferences = usePreferencesStore();
const { speciesNameMode } = storeToRefs(preferences);

const speciesNameSwitchValue = computed<boolean>({
    get: () => speciesNameMode.value === "vernacular",
    set: (value) => preferences.setSpeciesNameMode(value ? "vernacular" : "scientific"),
});

// --- Active page detection ---

function isActive(url: string): boolean {
    return route.path === url;
}

// --- Main nav items ---

const navItems = computed((): NavItem[] => {
    const items: NavItem[] = [
        {
            label: t("message.navExploreAllObservations"),
            url: config.urls.index,
            icon: "pi pi-map",
            showDot: false,
        },
        {
            label: t("message.navWhatsNew"),
            url: config.urls.news,
            icon: "pi pi-bell",
            showDot: config.user.hasUnseenNews,
        },
    ];

    if (config.user.isAuthenticated) {
        items.push({
            label: t("message.navMyAlerts"),
            url: config.urls.myAlerts,
            icon: "pi pi-exclamation-circle",
            showDot: config.user.hasAlertsWithUnseenObservations,
        });
    }

    items.push(
        {
            label: t("message.navAboutSite"),
            url: config.urls.aboutSite,
            icon: "pi pi-info-circle",
            showDot: false,
        },
        {
            label: t("message.navAboutData"),
            url: config.urls.aboutData,
            icon: "pi pi-database",
            showDot: false,
        },
    );

    return items;
});

// --- Language selector ---

const selectedLanguage = ref(config.currentLanguage);

function changeLanguage(event: { value: string }) {
    // POST to Django's set_language view, matching the behaviour of the old
    // Bootstrap form in _language_selector.html.
    const form = document.createElement("form");
    form.method = "POST";
    form.action = config.urls.setLanguage;

    const fields: Record<string, string> = {
        csrfmiddlewaretoken: getCsrf(),
        language: event.value,
        next: window.location.href,
    };

    for (const [name, value] of Object.entries(fields)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.appendChild(input);
    }

    document.body.appendChild(form);
    form.submit();
}

// --- User dropdown menu ---

const userMenuRef = ref();

const userMenuItems = computed((): NavItem[] => {
    const items: NavItem[] = [
        {
            label: t("message.navMyProfile"),
            icon: "pi pi-user",
            url: config.urls.profile,
        },
        {
            label: t("message.navApiTokens"),
            icon: "pi pi-key",
            url: "/api-tokens",
        },
        {
            label: t("message.navChangePassword"),
            icon: "pi pi-cog",
            url: config.urls.passwordChange,
        },
        {
            label: t("message.navMyAlerts"),
            icon: "pi pi-exclamation-circle",
            url: config.urls.myAlerts,
            showDot: config.user.hasAlertsWithUnseenObservations,
        },
        {
            label: t("message.navMyCustomAreas"),
            icon: "pi pi-map",
            url: config.urls.myCustomAreas,
        },
        { separator: true },
    ];

    if (config.user.isSuperuser) {
        items.push({
            label: t("message.navAdminPanel"),
            icon: "pi pi-key",
            url: config.urls.admin,
        });
    }

    items.push({
        label: t("message.navSignOut"),
        icon: "pi pi-power",
        url: config.urls.signout,
    });

    return items;
});

function toggleUserMenu(event: Event) {
    userMenuRef.value.toggle(event);
}
</script>

<template>
    <div class="gbif-navbar-wrapper">
        <Menubar :model="navItems">
            <template #start>
                <a :href="config.urls.index" class="gbif-navbar-brand">
                    <i class="pi pi-megaphone" />
                    {{ config.siteName }}
                </a>
            </template>

            <template #item="{ item, props }">
                <!--
                    props.action provides PrimeVue's own tabindex / aria attrs.
                    We add href and our active/dot logic on top.
                -->
                <a
                    v-bind="props.action"
                    :href="(item as NavItem).url"
                    :class="[
                        'gbif-nav-link',
                        { 'gbif-nav-active': isActive((item as NavItem).url ?? '') },
                    ]"
                >
                    <i v-if="item.icon" :class="item.icon"  />
                    <span>{{ item.label }}</span>
                    <span v-if="(item as NavItem).showDot" class="gbif-nav-dot" />
                </a>
            </template>

            <template #end>
                <div class="gbif-navbar-end">
                    <div
                        class="gbif-species-name-toggle"
                        :aria-label="t('message.speciesDisplayToggleLabel')"
                        :title="t('message.speciesDisplayToggleLabel')"
                    >
                        <span class="gbif-species-name-toggle-label" :class="{ 'is-active': !speciesNameSwitchValue }">
                            <em>{{ t("message.speciesDisplayShowScientific") }}</em>
                        </span>
                        <ToggleSwitch
                            v-model="speciesNameSwitchValue"
                            :aria-label="t('message.speciesDisplayToggleLabel')"
                        />
                        <span class="gbif-species-name-toggle-label" :class="{ 'is-active': speciesNameSwitchValue }">
                            {{ t("message.speciesDisplayShowVernacular") }}
                        </span>
                    </div>

                    <!-- Language selector: only shown when more than one language is enabled -->
                    <Select
                        v-if="config.enabledLanguages.length > 1"
                        v-model="selectedLanguage"
                        :options="config.enabledLanguages"
                        option-label="nameLocal"
                        option-value="code"
                        size="small"
                        class="gbif-lang-select"
                        @change="changeLanguage"
                    />

                    <!-- Authenticated user: dropdown menu -->
                    <template v-if="config.user.isAuthenticated">
                        <Button
                            :label="config.user.username ?? ''"
                            icon="pi pi-user"
                            text
                            class="gbif-navbar-user-btn"
                            @click="toggleUserMenu"
                        />
                        <Menu ref="userMenuRef" :model="userMenuItems" popup>
                            <template #item="{ item, props }">
                                <a v-bind="props.action" :href="(item as NavItem).url" class="gbif-user-menu-item">
                                    <i v-if="item.icon" :class="item.icon" />
                                    <span>{{ item.label }}</span>
                                    <span v-if="(item as NavItem).showDot" class="gbif-nav-dot gbif-nav-dot--menu" />
                                </a>
                            </template>
                        </Menu>
                    </template>

                    <!-- Anonymous user: sign in / sign up -->
                    <template v-else>
                        <Button
                            :label="t('message.navSignIn')"
                            icon="pi pi-lock"
                            size="small"
                            as="a"
                            :href="config.urls.signin"
                        />
                        <Button
                            :label="t('message.navSignUp')"
                            icon="pi pi-user-plus"
                            size="small"
                            outlined
                            as="a"
                            :href="config.urls.signup"
                        />
                    </template>
                </div>
            </template>
        </Menubar>
    </div>
</template>

<style scoped>
/*
 * Layout overrides for the menubar - colors are handled by the PrimeVue design
 * token preset built in main.ts from GBIF_ALERT["PRIMEVUE_PRIMARY_PALETTE"].
 */
:deep(.p-menubar) {
    border: none;
    border-radius: 0;
    padding: 0.5rem 1rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.gbif-navbar-brand {
    font-weight: bold;
    color: inherit;
    text-decoration: none;
    margin-right: 1.5rem;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.gbif-nav-link {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.gbif-nav-link.gbif-nav-active {
    font-weight: bold;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 0.35rem 0.6rem;
}

.gbif-navbar-end {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Red dot indicator for unseen items.
 * The box-shadow ring uses the PrimeVue contrast token (white on primary
 * backgrounds) so the dot stays visible against any primary palette color. */
.gbif-nav-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background-color: #ef4444;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 0 1.5px var(--p-primary-contrast-color);
}

.gbif-navbar-user-btn {
    color: inherit !important;
}

.gbif-user-menu-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
}

/* In the dropdown, drop the white ring (light background makes it invisible anyway) */
.gbif-nav-dot--menu {
    box-shadow: none;
    margin-left: auto;
}

/* Sign-in / sign-up buttons sit on the primary-colored navbar, so override
 * PrimeVue's default primary-colored button styles to use white instead. */
:deep(.gbif-navbar-end .p-button) {
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.7);
}
:deep(.gbif-navbar-end .p-button:hover) {
    background: rgba(255, 255, 255, 0.15);
    border-color: #ffffff;
}

.gbif-lang-select {
    /* Keep the language selector compact within the navbar */
    min-width: 0;
}

.gbif-species-name-toggle {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: #ffffff;
}

.gbif-species-name-toggle-label {
    font-size: 0.85rem;
    opacity: 0.55;
    transition: opacity 120ms ease;
}

.gbif-species-name-toggle-label.is-active {
    opacity: 1;
}
</style>
