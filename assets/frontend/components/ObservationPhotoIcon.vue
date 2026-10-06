<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Tooltip from "primevue/tooltip";
import type { components } from "../types/api";
import { imageTooltipHtml } from "../utils/imageTooltip";
import { licenseLabel } from "../utils/license";

defineOptions({ directives: { tooltip: Tooltip } });

// A camera marking an observation with photos; hovering it shows the first one.
// Renders nothing when the observation has none.
const props = defineProps<{
    image: components["schemas"]["ObservationImageOut"] | null;
}>();

const { t } = useI18n();

const tooltipBinding = computed(() => {
    const img = props.image;
    if (!img) return undefined;
    const license = licenseLabel(img.license);
    const credit =
        img.attribution || license
            ? t("message.speciesImageCredit", {
                  attribution: img.attribution || "?",
                  license: license || "?",
              })
            : "";
    const caption = t("message.observationPhoto");
    return {
        value: imageTooltipHtml({ url: img.thumbnailUrl, alt: caption, caption, credit }),
        escape: false,
    };
});
</script>

<template>
    <i
        v-if="image"
        v-tooltip.top="tooltipBinding"
        class="pi pi-camera observation-photo-icon"
        role="img"
        :aria-label="t('message.observationHasPhotos')"
    />
</template>

<style scoped>
.observation-photo-icon {
    color: var(--p-text-muted-color);
    cursor: help;
}
</style>
