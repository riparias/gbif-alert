<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import Drawer from "primevue/drawer";
import Select from "primevue/select";
import ToggleSwitch from "primevue/toggleswitch";
import { storeToRefs } from "pinia";
import type { NavItem } from "./navItems";
import { usePreferencesStore } from "../../stores/preferences";
import type { NavConfig } from "../../utils/navConfig";

/**
 * The navbar's small-screen form.
 *
 * PrimeVue's Menubar collapses its `model` into a hamburger on its own, but
 * leaves the `#end` slot (language, species-name toggle, sign in/out) inline,
 * which is what overflowed the bar. So on mobile we render our own drawer and
 * put everything in it, in one scrollable column.
 */
const props = defineProps<{
    visible: boolean;
    config: NavConfig;
    navItems: NavItem[];
    userMenuItems: NavItem[];
    isItemActive: (item: NavItem) => boolean;
}>();

const emit = defineEmits<{
    "update:visible": [value: boolean];
    navigate: [event: MouseEvent, url: string | undefined];
    "menu-item-click": [event: MouseEvent, item: NavItem];
    "change-language": [event: { value: string }];
}>();

const { t } = useI18n();

const preferences = usePreferencesStore();
const { speciesNameMode } = storeToRefs(preferences);

const speciesNameSwitchValue = computed<boolean>({
    get: () => speciesNameMode.value === "vernacular",
    set: (value) => preferences.setSpeciesNameMode(value ? "vernacular" : "scientific"),
});

// The submenu ("About") is flattened here: a nested accordion inside a drawer
// this short would be more chrome than the two entries are worth.
const flatNavItems = computed((): NavItem[] =>
    props.navItems.flatMap((item) => (item.items ? (item.items as NavItem[]) : [item])),
);
</script>

<template>
    <Drawer
        :visible="visible"
        position="right"
        class="gbif-mobile-nav-drawer"
        :header="config.siteName"
        @update:visible="(v: boolean) => emit('update:visible', v)"
    >
        <nav class="mobile-nav-section">
            <a
                v-for="item in flatNavItems"
                :key="item.label as string"
                :href="item.url"
                class="mobile-nav-link"
                :class="{ 'is-active': isItemActive(item) }"
                @click="emit('navigate', $event, item.url)"
            >
                <i v-if="item.icon" :class="item.icon" />
                <span>{{ item.label }}</span>
                <span v-if="item.showDot" class="mobile-nav-dot" />
            </a>
        </nav>

        <div class="mobile-nav-separator" />

        <div class="mobile-nav-section">
            <div class="mobile-nav-setting">
                <span class="mobile-nav-setting-label">
                    {{ t("message.speciesDisplayToggleLabel") }}
                </span>
                <!-- Unlike the navbar, which shows both options either side of
                     the switch, the drawer shows only the one in effect: the
                     two labels plus the switch need ~261px and the drawer gives
                     252px in English, less in French and Dutch. The section
                     heading above already says what the switch is for. -->
                <div class="mobile-species-toggle">
                    <ToggleSwitch
                        v-model="speciesNameSwitchValue"
                        :aria-label="t('message.speciesDisplayToggleLabel')"
                    />
                    <span class="mobile-species-toggle-value">
                        <template v-if="speciesNameSwitchValue">
                            {{ t("message.speciesDisplayShowVernacular") }}
                        </template>
                        <em v-else>{{ t("message.speciesDisplayShowScientific") }}</em>
                    </span>
                </div>
            </div>

            <div v-if="config.enabledLanguages.length > 1" class="mobile-nav-setting">
                <span class="mobile-nav-setting-label">{{ t("message.navLanguage") }}</span>
                <Select
                    :model-value="config.currentLanguage"
                    :options="config.enabledLanguages"
                    option-label="nameLocal"
                    option-value="code"
                    class="mobile-lang-select"
                    :aria-label="t('message.navLanguage')"
                    @change="(e) => emit('change-language', e)"
                />
            </div>
        </div>

        <div class="mobile-nav-separator" />

        <!-- Authenticated: the same entries as the desktop user dropdown -->
        <nav v-if="config.user.isAuthenticated" class="mobile-nav-section">
            <span class="mobile-nav-setting-label">{{ config.user.username }}</span>
            <template v-for="(item, index) in userMenuItems" :key="index">
                <div v-if="item.separator" class="mobile-nav-separator" />
                <a
                    v-else
                    :href="item.url"
                    class="mobile-nav-link"
                    @click="emit('menu-item-click', $event, item)"
                >
                    <i v-if="item.icon" :class="item.icon" />
                    <span>{{ item.label }}</span>
                    <span v-if="item.showDot" class="mobile-nav-dot" />
                </a>
            </template>
        </nav>

        <!-- Anonymous: sign in / sign up -->
        <div v-else class="mobile-nav-auth">
            <Button
                :label="t('message.navSignIn')"
                icon="pi pi-lock"
                as="a"
                :href="config.urls.signin"
                @click="emit('navigate', $event, config.urls.signin)"
            />
            <Button
                :label="t('message.navSignUp')"
                icon="pi pi-user-plus"
                outlined
                as="a"
                :href="config.urls.signup"
                @click="emit('navigate', $event, config.urls.signup)"
            />
        </div>
    </Drawer>
</template>

<style scoped>
.mobile-nav-section {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

/* Links are full-width rows with a comfortable touch target (44px minimum,
 * which is the smallest reliably tappable size on a phone). */
.mobile-nav-link {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    min-height: 44px;
    padding: 0.5rem 0.5rem;
    border-radius: 6px;
    color: var(--p-text-color);
    text-decoration: none;
}

.mobile-nav-link:hover {
    background: var(--p-content-hover-background);
}

.mobile-nav-link.is-active {
    font-weight: 700;
    color: var(--p-primary-color);
    background: var(--p-highlight-background, rgba(0, 0, 0, 0.04));
}

.mobile-nav-link .pi {
    width: 1.1rem;
    color: var(--p-text-muted-color);
}

.mobile-nav-link.is-active .pi {
    color: var(--p-primary-color);
}

.mobile-nav-dot {
    width: 8px;
    height: 8px;
    margin-left: auto;
    background-color: #ef4444;
    border-radius: 50%;
    flex-shrink: 0;
}

.mobile-nav-separator {
    border-top: 1px solid var(--p-content-border-color);
    margin: 0.75rem 0;
}

.mobile-nav-setting {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.5rem 0.5rem;
}

.mobile-nav-setting-label {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--p-text-muted-color);
}

.mobile-species-toggle {
    display: flex;
    align-items: center;
    gap: 0.6rem;
}

.mobile-species-toggle-value {
    font-size: 0.9rem;
    font-weight: 600;
}

.mobile-lang-select {
    width: 100%;
}

.mobile-nav-auth {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
</style>
