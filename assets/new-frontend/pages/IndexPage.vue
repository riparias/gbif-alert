<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import Card from "primevue/card";
import FilterPanel from "../components/FilterPanel.vue";
import ObservationsView from "../components/ObservationsView.vue";
import { useFilterSync } from "../composables/useFilterSync";
import { getNavConfig } from "../utils/navConfig";

const { t } = useI18n();
const route = useRoute();

useFilterSync();

const navConfig = getNavConfig();
const isAuthenticated: boolean = navConfig.user.isAuthenticated;
document.title = `${t("message.home")} - ${navConfig.siteName}`;

// Enable smart unseen fallback only when the user hasn't explicitly set a status filter
// via the URL (i.e. the default "unseen" view, not a deliberate "all" bookmark).
const unseenFallback = computed(() => isAuthenticated && !route.query.status);

// Welcome text: page fragment rendered server-side, language-aware
const welcomeHtml = ref("");
async function loadWelcomeText() {
    const resp = await fetch("/api/v2/page-fragments/welcome_text/");
    if (resp.ok) {
        const data = await resp.json();
        welcomeHtml.value = data.html;
    }
}

onMounted(() => {
    loadWelcomeText();
});
</script>

<template>
    <div class="page-content index-page">
        <!-- Welcome text (page fragment, rendered HTML from backend) -->
        <div v-if="welcomeHtml" class="welcome-text" v-html="welcomeHtml" />

        <!-- Filters -->
        <Card>
            <template #title><i class="pi pi-filter" /> {{ t("message.filters") }}</template>
            <template #content>
                <FilterPanel />
            </template>
        </Card>

        <!-- Observation view: counter, histogram, map, table, drawer -->
        <ObservationsView :unseen-fallback="unseenFallback" />
    </div>
</template>

<style scoped>
.index-page {
    /* Card's own body-padding already separates content from the navbar;
       removing top padding avoids the double gap that makes the index page
       look like it starts too far down. */
    padding-top: 0;
}

.welcome-text :deep(p) { margin: 0 0 0.75rem; }
.welcome-text :deep(p:last-child) { margin-bottom: 0; }
</style>
