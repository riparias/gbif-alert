<script setup lang="ts">
import { useI18n } from "vue-i18n";

defineProps<{ count: number; loading: boolean }>();

const { t } = useI18n();
</script>

<template>
    <div class="observation-counter">
        <span v-if="loading" class="counter-loading">...</span>
        <span v-else class="counter-value">
            {{ t("message.matchingObservations", count, { count }) }}
        </span>
    </div>
</template>

<style scoped>
.observation-counter {
    font-size: 1rem;
    font-weight: 600;
}

.counter-loading {
    color: var(--p-text-muted-color);
}
</style>
