<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import FilterSidebar from "../components/FilterSidebar.vue";
import HistogramBrush from "../components/HistogramBrush.vue";
import ObservationsView from "../components/ObservationsView.vue";
import { useFilterSync } from "../composables/useFilterSync";
import { getNavConfig } from "../utils/navConfig";
import { useResultsStore } from "../stores/results";

const { t } = useI18n();
const route = useRoute();

const resultsStore = useResultsStore();
resultsStore.loading = true;

useFilterSync();

const navConfig = getNavConfig();
const isAuthenticated: boolean = navConfig.user.isAuthenticated;
document.title = `${t("message.home")} - ${navConfig.siteName}`;

const unseenFallback = computed(() => isAuthenticated && !route.query.status);
</script>

<template>
    <div class="experiment-layout">
        <aside class="experiment-sidebar">
            <FilterSidebar />
        </aside>

        <div class="experiment-main">
            <HistogramBrush />
            <ObservationsView variant="experiment" :unseen-fallback="unseenFallback" />
        </div>
    </div>
</template>

<style scoped>
.experiment-layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: 1rem;
    padding: 1rem;
    min-height: 0;
}

.experiment-sidebar {
    /* Sticky so the sidebar stays in view while the user scrolls results */
    position: sticky;
    top: 1rem;
    height: fit-content;
    background: #1e293b;
    border-radius: 8px;
    overflow: hidden;
}

.experiment-main {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 0; /* prevent CSS grid blowout */
}
</style>
