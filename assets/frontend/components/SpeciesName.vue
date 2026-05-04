<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Tooltip from "primevue/tooltip";
import { usePreferencesStore } from "../stores/preferences";
import { getNavConfig } from "../utils/navConfig";

defineOptions({ directives: { tooltip: Tooltip } });

const props = defineProps<{
    scientificName: string;
    vernacularName: string;
}>();

const preferences = usePreferencesStore();
const { t } = useI18n();

const navConfig = getNavConfig();

const activeLanguageNameLocal = computed(() => {
    const lang = navConfig.enabledLanguages.find(
        (l) => l.code === navConfig.currentLanguage,
    );
    return lang ? lang.nameLocal : navConfig.currentLanguage;
});

// Three render variants:
//   "scientific"             - mode=scientific, popover shows vernacular (or fallback msg)
//   "vernacular"             - mode=vernacular and vernacular present, popover shows scientific
//   "vernacular-fallback"    - mode=vernacular but vernacular missing, popover shows fallback msg
type Variant = "scientific" | "vernacular" | "vernacular-fallback";

const variant = computed<Variant>(() => {
    if (preferences.speciesNameMode === "scientific") return "scientific";
    return props.vernacularName ? "vernacular" : "vernacular-fallback";
});

function escapeHtml(s: string): string {
    return s
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// PrimeVue's v-tooltip accepts an object with `escape: false` to render HTML.
// We use it only to italicise the scientific name; all interpolated values are
// HTML-escaped first.
const tooltipBinding = computed(() => {
    if (variant.value === "scientific") {
        return props.vernacularName
            ? { value: props.vernacularName, escape: true }
            : {
                  value: t("message.noVernacularAvailable", {
                      language: activeLanguageNameLocal.value,
                  }),
                  escape: true,
              };
    }
    if (variant.value === "vernacular") {
        return { value: `<em>${escapeHtml(props.scientificName)}</em>`, escape: false };
    }
    // vernacular-fallback
    return {
        value: t("message.noVernacularAvailable", { language: activeLanguageNameLocal.value }),
        escape: true,
    };
});
</script>

<template>
    <span v-tooltip.top="tooltipBinding" class="species-name">
        <em v-if="variant === 'scientific'">{{ scientificName }}</em>
        <template v-else-if="variant === 'vernacular'">{{ vernacularName }}</template>
        <template v-else>
            <em>{{ scientificName }}</em>
            <i class="pi pi-info-circle species-name-fallback-icon" aria-hidden="true" />
        </template>
    </span>
</template>

<style scoped>
.species-name {
    text-decoration: underline dotted;
    text-decoration-color: var(--p-text-muted-color, #999);
    text-underline-offset: 2px;
    cursor: help;
}

.species-name-fallback-icon {
    margin-left: 0.25em;
    font-size: 0.85em;
    opacity: 0.6;
}
</style>
