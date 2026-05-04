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

const tooltipText = computed(() => {
    if (variant.value === "scientific") {
        return props.vernacularName
            ? props.vernacularName
            : t("message.noVernacularAvailable", { language: activeLanguageNameLocal.value });
    }
    if (variant.value === "vernacular") {
        return props.scientificName;
    }
    // vernacular-fallback
    return t("message.noVernacularAvailable", { language: activeLanguageNameLocal.value });
});
</script>

<template>
    <span v-tooltip.top="tooltipText" class="species-name">
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
