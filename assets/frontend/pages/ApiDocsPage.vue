<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import Card from "primevue/card";
import Button from "primevue/button";

const { t } = useI18n();
const version = ref<string | null>(null);

onMounted(async () => {
    // The live version is a nice-to-have freshness touch, not load-critical.
    try {
        const resp = await fetch("/api/v2/openapi.json");
        if (resp.ok) {
            const schema = await resp.json();
            version.value = schema?.info?.version ?? null;
        }
    } catch {
        /* ignore - the page works without the version */
    }
});
</script>

<template>
    <div class="page-content--wide">
        <h1 style="margin-bottom: 1rem;">{{ t("message.apiPageTitle") }}</h1>
        <p>{{ t("message.apiPageIntro") }}</p>

        <Card class="api-card">
            <template #title>
                {{ t("message.apiV2Title") }}
                <span v-if="version" class="api-version">
                    {{ t("message.apiVersionLabel") }} {{ version }}
                </span>
            </template>
            <template #content>
                <p>{{ t("message.apiV2Desc") }}</p>
                <a href="/api/v2/docs">
                    <Button :label="t('message.apiV2DocsLink')" icon="pi pi-book" size="small" />
                </a>
            </template>
        </Card>

        <Card class="api-card">
            <template #title>{{ t("message.apiAuthTitle") }}</template>
            <template #content>
                <p>{{ t("message.apiAuthDesc") }}</p>
            </template>
        </Card>

        <Card class="api-card">
            <template #title>{{ t("message.apiWfsTitle") }}</template>
            <template #content>
                <p>{{ t("message.apiWfsDesc") }}</p>
                <a href="/api/wfs/observations">
                    <Button
                        :label="t('message.apiWfsLink')"
                        icon="pi pi-map"
                        size="small"
                        severity="secondary"
                    />
                </a>
            </template>
        </Card>

        <Card class="api-card">
            <template #title>{{ t("message.apiLegacyTitle") }}</template>
            <template #content>
                <p>{{ t("message.apiLegacyDesc") }}</p>
            </template>
        </Card>

        <p class="api-internal-note">{{ t("message.apiInternalNote") }}</p>
    </div>
</template>

<style scoped>
.api-card {
    margin-top: 1rem;
}

.api-version {
    font-size: 0.8rem;
    font-weight: 400;
    color: var(--p-text-muted-color);
    margin-left: 0.5rem;
}

.api-internal-note {
    margin-top: 1.5rem;
    font-size: 0.85rem;
    color: var(--p-text-muted-color);
}
</style>
