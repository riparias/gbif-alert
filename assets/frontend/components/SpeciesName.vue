<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Tooltip from "primevue/tooltip";
import { usePreferencesStore } from "../stores/preferences";
import { useFilterOptionsStore } from "../stores/filterOptions";
import { getNavConfig } from "../utils/navConfig";

defineOptions({ directives: { tooltip: Tooltip } });

const props = defineProps<{
    scientificName: string;
    vernacularName: string;
}>();

const preferences = usePreferencesStore();
const filterOptions = useFilterOptionsStore();
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

// Look up the matched species from the filter options store and return image
// fields when available; null otherwise.
const speciesImage = computed(() => {
    const match = filterOptions.species.find(
        (s) => s.scientificName === props.scientificName,
    );
    if (!match || !match.imageUrl) return null;
    return {
        url: match.imageUrl,
        attribution: match.imageAttribution,
        license: match.imageLicense,
    };
});

// Build the image + credit HTML to prepend to the tooltip, or "" when there
// is no image. All interpolated values are HTML-escaped.
function imageTooltipHtml(): string {
    const img = speciesImage.value;
    if (!img) return "";
    const credit =
        img.attribution || img.license
            ? `<div class="species-tooltip-credit">${escapeHtml(
                  t("message.speciesImageCredit", {
                      attribution: img.attribution || "?",
                      license: img.license || "?",
                  }),
              )}</div>`
            : "";
    // onerror hides a dead hotlink instead of showing a broken-image icon.
    return (
        `<img src="${escapeHtml(img.url)}" class="species-tooltip-img" ` +
        `onerror="this.style.display='none'" />${credit}`
    );
}

// PrimeVue's v-tooltip accepts an object with `escape: false` to render HTML.
// We use it only to italicise the scientific name; all interpolated values are
// HTML-escaped first.

// baseTooltip() returns the tooltip binding for the current variant, with
// no image included. This preserves the original behavior byte-for-byte.
function baseTooltip(): { value: string; escape: boolean } {
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
}

const tooltipBinding = computed(() => {
    const imageHtml = imageTooltipHtml();
    const base = baseTooltip();
    if (!imageHtml) return base;
    // With an image we must render HTML; escape the base text ourselves.
    const baseValue =
        base.escape === false ? base.value : escapeHtml(String(base.value));
    return { value: `${imageHtml}<div>${baseValue}</div>`, escape: false };
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
