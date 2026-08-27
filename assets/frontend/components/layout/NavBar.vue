<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import Menubar from "primevue/menubar";
import Button from "primevue/button";
import Select from "primevue/select";
import Menu from "primevue/menu";
import ToggleSwitch from "primevue/toggleswitch";
import { storeToRefs } from "pinia";
import MobileNavDrawer from "./MobileNavDrawer.vue";
import type { NavItem } from "./navItems";
import { getNavConfig } from "../../utils/navConfig";
import { getCsrf } from "../../utils/csrf";
import { useBreakpoint } from "../../composables/useBreakpoint";
import { usePreferencesStore } from "../../stores/preferences";
import { useUserStore } from "../../stores/user";

// --- Config ---

const config = getNavConfig();
// The notification dots come from the store, not from `config`: the nav config
// is a page-load snapshot, so a dot read from it stays lit until a full reload
// (e.g. after visiting the news page).
const userStore = useUserStore();
const route = useRoute();
const router = useRouter();
const { t } = useI18n();

// --- Client-side navigation ---
//
// Every nav link keeps a real `href` so middle-click / Cmd-click / "open in
// new tab" and accessibility behave normally. For ordinary left-clicks we
// intercept and let Vue Router swap the page in place (no full reload, no
// blink) - but only when the target actually resolves to an SPA route.
// Genuinely external Django pages (/admin/, sign-out) resolve to the named
// "not-found" catch-all, so they fall through to a normal full navigation.

function isInternal(url: string | undefined): boolean {
    return url !== undefined && router.resolve(url).name !== "not-found";
}

function onNavClick(event: MouseEvent, url: string | undefined): void {
    // Mirror what <router-link> does: never hijack a click the user meant to
    // open in a new tab/window, nor one already handled.
    if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
    ) {
        return;
    }

    if (isInternal(url)) {
        event.preventDefault();
        router.push(url as string);
    }
}

// User-menu items are either links (they carry a `url`) or actions (they carry
// a `command`, e.g. sign out). Actions run their handler instead of navigating.
function onUserMenuItemClick(event: MouseEvent, item: NavItem): void {
    if (item.command) {
        event.preventDefault();
        item.command({ originalEvent: event, item });
        return;
    }
    onNavClick(event, item.url);
}

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

// A parent item (e.g. "About") has no page of its own, so it counts as active
// while the user is on any of its children.
function isItemActive(item: NavItem): boolean {
    if (item.items) {
        return (item.items as NavItem[]).some((child) => isActive(child.url ?? ""));
    }
    return isActive(item.url ?? "");
}

// --- Main nav items ---

const navItems = computed((): NavItem[] => {
    const items: NavItem[] = [
        {
            // Short label: the navbar is tight. The full wording is kept for the
            // 404 page, where it reads as a sentence rather than a nav entry.
            label: t("message.navExplore"),
            url: config.urls.index,
            icon: "pi pi-map",
            showDot: false,
        },
        {
            label: t("message.navWhatsNew"),
            url: config.urls.news,
            icon: "pi pi-bell",
            showDot: userStore.hasUnseenNews,
        },
    ];

    if (config.user.isAuthenticated) {
        items.push({
            label: t("message.navMyAlerts"),
            url: config.urls.myAlerts,
            icon: "pi pi-exclamation-circle",
            showDot: userStore.hasAlertsWithUnseenObservations,
        });
    }

    // The two "about" pages live in a submenu rather than at the top level.
    // The parent is not a link of its own (there is no "about" landing page):
    // clicking it opens the submenu, which is PrimeVue's default for an item
    // with children.
    items.push({
        label: t("message.navAbout"),
        icon: "pi pi-info-circle",
        items: [
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
        ],
    });

    return items;
});

// --- Language selector ---

const selectedLanguage = ref(config.currentLanguage);

// Collapsed, the selector shows the bare language code ("EN"). Django can hand
// us a regional code (e.g. "en-us"), which would render as "EN-US", so keep the
// base subtag only.
function shortLanguageCode(value: string | null | undefined): string {
    return (value ?? config.currentLanguage).split("-")[0].toUpperCase();
}

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
            showDot: userStore.hasAlertsWithUnseenObservations,
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
        command: signout,
    });

    return items;
});

// Sign out via the API (a session-ending POST), then reload into the anonymous
// homepage. A plain GET link cannot be used: Django's LogoutView returns 405
// for anything but POST.
async function signout(): Promise<void> {
    await fetch("/api/v2/auth/signout/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf() },
    });
    window.location.href = "/";
}

function toggleUserMenu(event: Event) {
    userMenuRef.value.toggle(event);
}

// --- Mobile ---

const { isMobile } = useBreakpoint();
const mobileMenuOpen = ref(false);

// Any dot at all, shown on the closed hamburger: with the entries hidden behind
// it, a per-item dot would otherwise be invisible until the drawer is opened.
const hasAnyDot = computed(
    () => userStore.hasUnseenNews || userStore.hasAlertsWithUnseenObservations,
);

// A drawer left open across a navigation would cover the page the user just
// asked for.
watch(
    () => route.path,
    () => (mobileMenuOpen.value = false),
);
</script>

<template>
    <div class="gbif-navbar-wrapper">
        <Menubar v-if="!isMobile" :model="navItems">
            <template #start>
                <a
                    :href="config.urls.index"
                    class="gbif-navbar-brand"
                    @click="onNavClick($event, config.urls.index)"
                >
                    <i class="pi pi-megaphone" />
                    {{ config.siteName }}
                </a>
            </template>

            <template #item="{ item, props, root, hasSubmenu }">
                <!--
                    props.action provides PrimeVue's own tabindex / aria attrs.
                    We add href and our active/dot logic on top. A custom item
                    template also replaces PrimeVue's built-in submenu arrow, so
                    we render it ourselves when the item has children.
                -->
                <a
                    v-bind="props.action"
                    :href="(item as NavItem).url"
                    :class="[
                        'gbif-nav-link',
                        root ? 'gbif-nav-root-link' : 'gbif-nav-sub-link',
                        { 'gbif-nav-active': isItemActive(item as NavItem) },
                    ]"
                    @click="onNavClick($event, (item as NavItem).url)"
                >
                    <i v-if="item.icon" :class="item.icon" />
                    <span>{{ item.label }}</span>
                    <span v-if="(item as NavItem).showDot" class="gbif-nav-dot" />
                    <i v-if="hasSubmenu" class="pi pi-angle-down gbif-nav-submenu-icon" />
                </a>
            </template>

            <template #end>
                <div class="gbif-navbar-end">
                    <div
                        class="gbif-species-name-toggle"
                        :aria-label="t('message.speciesDisplayToggleLabel')"
                        :title="t('message.speciesDisplayToggleLabel')"
                    >
                        <span
                            class="gbif-species-name-toggle-label"
                            :class="{ 'is-active': !speciesNameSwitchValue }"
                        >
                            <em>{{ t("message.speciesDisplayShowScientific") }}</em>
                        </span>
                        <ToggleSwitch
                            v-model="speciesNameSwitchValue"
                            :aria-label="t('message.speciesDisplayToggleLabel')"
                        />
                        <span
                            class="gbif-species-name-toggle-label"
                            :class="{ 'is-active': speciesNameSwitchValue }"
                        >
                            {{ t("message.speciesDisplayShowVernacular") }}
                        </span>
                    </div>

                    <!-- Language selector: only shown when more than one language is enabled.
                         Collapsed it is just a globe + the language code, to keep the navbar
                         narrow; the overlay is widened (see .gbif-lang-overlay) so the full
                         native names still fit. -->
                    <Select
                        v-if="config.enabledLanguages.length > 1"
                        v-model="selectedLanguage"
                        :options="config.enabledLanguages"
                        option-label="nameLocal"
                        option-value="code"
                        size="small"
                        class="gbif-lang-select"
                        overlay-class="gbif-lang-overlay"
                        :aria-label="t('message.navLanguage')"
                        @change="changeLanguage"
                    >
                        <template #value="{ value }">
                            <span class="gbif-lang-value">
                                <i class="pi pi-globe" />
                                {{ shortLanguageCode(value) }}
                            </span>
                        </template>
                    </Select>

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
                                <a
                                    v-bind="props.action"
                                    :href="(item as NavItem).url"
                                    class="gbif-user-menu-item"
                                    @click="onUserMenuItemClick($event, item as NavItem)"
                                >
                                    <i v-if="item.icon" :class="item.icon" />
                                    <span>{{ item.label }}</span>
                                    <span
                                        v-if="(item as NavItem).showDot"
                                        class="gbif-nav-dot gbif-nav-dot--menu"
                                    />
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
                            @click="onNavClick($event, config.urls.signin)"
                        />
                        <Button
                            :label="t('message.navSignUp')"
                            icon="pi pi-user-plus"
                            size="small"
                            outlined
                            as="a"
                            :href="config.urls.signup"
                            @click="onNavClick($event, config.urls.signup)"
                        />
                    </template>
                </div>
            </template>
        </Menubar>

        <!-- Mobile: brand + hamburger only; everything else lives in the drawer. -->
        <div v-else class="gbif-mobile-bar">
            <a
                :href="config.urls.index"
                class="gbif-navbar-brand gbif-mobile-brand"
                @click="onNavClick($event, config.urls.index)"
            >
                <i class="pi pi-megaphone" />
                <span class="gbif-mobile-brand-text">{{ config.siteName }}</span>
            </a>

            <button
                type="button"
                class="gbif-hamburger"
                :aria-label="t('message.navOpenMenu')"
                :aria-expanded="mobileMenuOpen"
                @click="mobileMenuOpen = true"
            >
                <i class="pi pi-bars" />
                <span v-if="hasAnyDot" class="gbif-nav-dot gbif-hamburger-dot" />
            </button>
        </div>

        <MobileNavDrawer
            v-if="isMobile"
            v-model:visible="mobileMenuOpen"
            :config="config"
            :nav-items="navItems"
            :user-menu-items="userMenuItems"
            :is-item-active="isItemActive"
            @navigate="onNavClick"
            @menu-item-click="onUserMenuItemClick"
            @change-language="changeLanguage"
        />
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

/* --- Mobile bar (below 768px; see composables/useBreakpoint.ts) --- */

.gbif-mobile-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 1rem;
    background: var(--p-primary-color);
    color: var(--p-primary-contrast-color);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.gbif-mobile-brand {
    /* min-width:0 lets the flex child shrink below its content width, which is
     * what makes the ellipsis below possible: without it the long site name
     * ("LIFE RIPARIAS early alert") pushes the hamburger off-screen. */
    min-width: 0;
    margin-right: 0;
}

.gbif-mobile-brand-text {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

.gbif-hamburger {
    all: unset;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    /* 44px: the smallest comfortably tappable target on a phone. */
    width: 44px;
    height: 44px;
    flex-shrink: 0;
    border-radius: 6px;
    cursor: pointer;
    color: var(--p-primary-contrast-color);
}

.gbif-hamburger:hover,
.gbif-hamburger:focus-visible {
    background: rgba(255, 255, 255, 0.15);
}

.gbif-hamburger .pi-bars {
    font-size: 1.35rem;
}

.gbif-hamburger-dot {
    position: absolute;
    top: 6px;
    right: 6px;
}

.gbif-nav-link {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.gbif-nav-link.gbif-nav-active {
    font-weight: bold;
}

/* The active highlight is a pill drawn on the primary-colored bar, so it only
 * applies to top-level entries. Its padding is ours to set: bar items have no
 * padding of their own. */
.gbif-nav-root-link.gbif-nav-active {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 0.35rem 0.6rem;
}

/* Submenu items ("About this site" / "About the data") are rendered on the
 * light dropdown panel, but they are still inside .p-menubar, which paints its
 * links white for the primary-colored bar - so without this they would be white
 * on white. The active one gets the primary color: the translucent white pill
 * above would be invisible here, and PrimeVue already pads these links, so
 * restyling them would knock the active row out of line with the others. */
.gbif-nav-sub-link {
    color: var(--p-text-color);
}

.gbif-nav-sub-link.gbif-nav-active {
    color: var(--p-primary-color);
}

.gbif-nav-submenu-icon {
    font-size: 0.75rem;
    margin-left: 0.15rem;
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
    /* Keep the language selector compact within the navbar: collapsed it only
     * holds a globe and a two-letter code, so it should shrink to that. The
     * full language names live in the overlay, which is widened separately
     * (:overlay-style above) and is not constrained by the trigger width. */
    min-width: 0;
    width: auto;
}

/* Trim PrimeVue's default trigger padding: sized for a full word, it leaves a
 * lot of air around a two-letter code. */
:deep(.gbif-lang-select .p-select-label) {
    padding: 0.25rem 0.4rem;
}

:deep(.gbif-lang-select .p-select-dropdown) {
    width: 1.5rem;
}

.gbif-lang-value {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    white-space: nowrap;
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

<!--
    The language dropdown's overlay is teleported to <body>, so a scoped style
    cannot reach it. PrimeVue also sets the overlay's min-width inline (to the
    trigger's width) when aligning it, which an inline style always wins - hence
    !important, without which the panel would shrink to the collapsed trigger
    and clip the language names.
-->
<style>
.gbif-lang-overlay {
    min-width: 10rem !important;
}
</style>
