<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import ProgressSpinner from "primevue/progressspinner";
import { getCsrf } from "../utils/csrf";

const { t } = useI18n();
const html = ref<string | null>(null);
const loading = ref(true);

onMounted(async () => {
    // Fire and forget - mark news as visited without blocking the UI
    fetch("/api/v2/spa/news/mark-visited/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf() },
    });

    const resp = await fetch("/api/v2/spa/page-fragments/news_page_content/");
    if (resp.ok) {
        const data = await resp.json();
        html.value = data.html;
    }
    loading.value = false;
});
</script>

<template>
    <div class="page-content--wide">
        <h1 style="margin-bottom: 1.5rem;">{{ t("message.whatsNew") }}</h1>
        <ProgressSpinner v-if="loading" />
        <div v-else v-html="html" />
    </div>
</template>
