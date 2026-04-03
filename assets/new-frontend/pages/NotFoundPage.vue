<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
    <div class="not-found-page">
        <h1>404</h1>
        <p>{{ t("message.pageNotFound") }}</p>
        <a href="/">{{ t("message.navExploreAllObservations") }}</a>
    </div>
</template>

<style scoped>
.not-found-page {
    padding: 4rem 2rem;
    text-align: center;
}
</style>
