<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import FilterSidebar from "../components/FilterSidebar.vue";
import ActiveFilterChips from "../components/ActiveFilterChips.vue";
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

const welcomeHtml = ref("");
onMounted(async () => {
    const resp = await fetch("/api/v2/page-fragments/welcome_text/");
    if (resp.ok) {
        const data = await resp.json();
        welcomeHtml.value = data.html;
    }
});
</script>

<template>
    <div class="index-layout">
        <aside class="index-sidebar">
            <FilterSidebar />
        </aside>

        <div class="index-main">
            <div v-if="welcomeHtml" class="welcome-text" v-html="welcomeHtml" />
            <HistogramBrush />
            <ActiveFilterChips />
            <ObservationsView variant="sidebar" :unseen-fallback="unseenFallback" />
        </div>
    </div>
</template>

<style scoped>
.index-layout {
    display: grid;
    grid-template-columns: 310px 1fr;
    gap: 1rem;
    padding: 1rem;
    min-height: 0;
}

.index-sidebar {
    /* Sticky so the sidebar stays in view while the user scrolls results */
    position: sticky;
    top: 1rem;
    height: fit-content;
    background: #1e293b;
    overflow: hidden;
}

.index-main {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 0; /* prevent CSS grid blowout */
}

.welcome-text :deep(p) { margin: 0 0 0.5rem; font-size: 0.9rem; }
.welcome-text :deep(p:last-child) { margin-bottom: 0; }
</style>
