<script setup lang="ts">
import Tooltip from "primevue/tooltip";

defineOptions({ directives: { tooltip: Tooltip } });

// A question mark placed next to a field label; hovering or focusing it shows
// a short explanation. Added only where a field needs one (#472).
defineProps<{ text: string }>();
</script>

<template>
    <i
        v-tooltip.top="text"
        class="pi pi-question-circle field-help"
        tabindex="0"
        role="img"
        :aria-label="text"
    />
</template>

<style scoped>
.field-help {
    font-size: 0.85em;
    color: var(--p-text-muted-color);
    cursor: help;
}
</style>
