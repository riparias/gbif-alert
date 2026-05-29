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

const navConfig = getNavConfig();
const isAuthenticated: boolean = navConfig.user.isAuthenticated;
document.title = `${t("message.home")} - ${navConfig.siteName}`;

useFilterSync(isAuthenticated);

const unseenFallback = computed(() => isAuthenticated && !route.query.status);

const welcomeHtml = ref("");
onMounted(async () => {
    const resp = await fetch("/api/v2/spa/page-fragments/welcome_text/");
    if (resp.ok) {
        const data = await resp.json();
        welcomeHtml.value = data.html;
    }
});
</script>

<template>
    <div class="sidebar-layout">
        <aside class="sidebar-layout__aside">
            <FilterSidebar />
        </aside>

        <div class="sidebar-layout__main">
            <div v-if="welcomeHtml" class="welcome-text" v-html="welcomeHtml" />
            <HistogramBrush />
            <ActiveFilterChips />
            <ObservationsView :unseen-fallback="unseenFallback" />
        </div>
    </div>
</template>

<style scoped>
.welcome-text :deep(p) { margin: 0 0 0.5rem; font-size: 0.9rem; }
.welcome-text :deep(p:last-child) { margin-bottom: 0; }
</style>
