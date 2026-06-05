<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import ProgressSpinner from "primevue/progressspinner";
import { getCsrf } from "../utils/csrf";
import { getNavConfig } from "../utils/navConfig";
import type { components } from "../types/api";

type ApiTokenOut = components["schemas"]["ApiTokenOut"];

const { t } = useI18n();
const router = useRouter();
const toast = useToast();
const confirm = useConfirm();

const isAuthenticated: boolean = getNavConfig().user?.isAuthenticated ?? false;

const loading = ref(true);
const tokens = ref<ApiTokenOut[]>([]);
const newTokenName = ref("");
const creatingToken = ref(false);
// The raw value of a just-created token, shown once.
const createdToken = ref<string | null>(null);

// A ready-to-run sample using the freshly created token and this site's host.
const sampleCurl = computed(() =>
    createdToken.value
        ? `curl -H "Authorization: Bearer ${createdToken.value}" ${window.location.origin}/api/v2/alerts/`
        : ""
);

onMounted(async () => {
    if (!isAuthenticated) {
        router.push("/accounts/signin/");
        return;
    }
    await loadTokens();
    loading.value = false;
});

async function loadTokens() {
    const resp = await fetch("/api/v2/api-tokens/");
    if (resp.ok) tokens.value = await resp.json();
}

async function createToken() {
    creatingToken.value = true;
    createdToken.value = null;
    try {
        const resp = await fetch("/api/v2/api-tokens/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
            body: JSON.stringify({ name: newTokenName.value.trim() }),
        });
        if (resp.ok) {
            const data = await resp.json();
            createdToken.value = data.token; // shown once
            newTokenName.value = "";
            await loadTokens();
        }
    } finally {
        creatingToken.value = false;
    }
}

function requestRevokeToken(token: ApiTokenOut) {
    confirm.require({
        message: t("message.confirmRevokeToken"),
        header: token.name || token.prefix,
        icon: "pi pi-exclamation-triangle",
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: () => revokeToken(token.id),
    });
}

async function revokeToken(id: number) {
    const resp = await fetch(`/api/v2/api-tokens/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrf() },
    });
    if (resp.status === 204) {
        await loadTokens();
        toast.add({ severity: "success", summary: t("message.apiTokenRevoked"), life: 3000 });
    }
}

async function copyText(text: string) {
    await navigator.clipboard?.writeText(text).catch(() => {});
    toast.add({ severity: "success", summary: t("message.apiTokenCopied"), life: 2000 });
}

function formatDate(iso: string | null): string {
    return iso ? new Date(iso).toLocaleDateString() : t("message.never");
}
</script>

<template>
    <div class="page-content--wide">
        <h1 style="margin-bottom: 0.5rem;">{{ t("message.apiTokensTitle") }}</h1>
        <p style="color: var(--p-text-muted-color); margin-bottom: 0.5rem;">
            {{ t("message.apiTokensIntro") }}
        </p>
        <p style="margin-bottom: 1.25rem;">
            <router-link to="/api-docs">{{ t("message.apiTokenSeeDocs") }}</router-link>
        </p>

        <ProgressSpinner v-if="loading" />

        <template v-else>
            <!-- Just-created token, shown once, with a ready-to-run sample -->
            <div v-if="createdToken" class="created-token">
                <small style="color: var(--p-orange-600); font-weight: 500;">
                    {{ t("message.apiTokenCreatedWarning") }}
                </small>
                <div class="copy-row">
                    <InputText :value="createdToken" readonly class="w-full" data-testid="created-token-value" />
                    <Button icon="pi pi-copy" :label="t('message.copyToken')" size="small" @click="copyText(createdToken)" />
                </div>

                <p class="usage-hint">{{ t("message.apiTokenUsageHint") }}</p>
                <div class="copy-row">
                    <pre class="sample-curl" data-testid="sample-curl">{{ sampleCurl }}</pre>
                    <Button icon="pi pi-copy" :label="t('message.copyCommand')" size="small" @click="copyText(sampleCurl)" />
                </div>
            </div>

            <!-- Existing tokens -->
            <ul v-if="tokens.length" class="token-list">
                <li v-for="tk in tokens" :key="tk.id" class="token-row">
                    <div>
                        <span style="font-weight: 500;">{{ tk.name || tk.prefix }}</span>
                        <code class="prefix">{{ tk.prefix }}&hellip;</code>
                        <br />
                        <small style="color: var(--p-text-muted-color);">
                            {{ t("message.apiTokenLastUsed") }} {{ formatDate(tk.lastUsedAt) }}
                        </small>
                    </div>
                    <Button
                        :label="t('message.revoke')"
                        severity="danger"
                        text
                        size="small"
                        @click="requestRevokeToken(tk)"
                    />
                </li>
            </ul>
            <p v-else class="muted">{{ t("message.noApiTokens") }}</p>

            <!-- Create -->
            <div class="copy-row" style="margin-top: 0.75rem;">
                <InputText
                    v-model="newTokenName"
                    :placeholder="t('message.apiTokenNamePlaceholder')"
                    class="w-full"
                />
                <Button
                    :label="t('message.createApiToken')"
                    icon="pi pi-plus"
                    size="small"
                    :loading="creatingToken"
                    @click="createToken"
                />
            </div>
        </template>
    </div>
</template>

<style scoped>
.created-token {
    border: 1px solid var(--p-content-border-color);
    border-radius: 6px;
    padding: 0.75rem;
    margin-bottom: 1.25rem;
    background: var(--p-surface-50);
}

.copy-row {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
    margin-top: 0.25rem;
}

/* Let the text field grow to fill the row (the page-level w-full utility is not
   available here, so the input would otherwise stay at its default width). */
.copy-row :deep(.p-inputtext) {
    flex: 1;
    min-width: 0;
}

.usage-hint {
    margin: 0.75rem 0 0.25rem;
    font-size: 0.875rem;
}

.sample-curl {
    flex: 1;
    margin: 0;
    padding: 0.5rem;
    background: var(--p-surface-100);
    border-radius: 4px;
    font-size: 0.8rem;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

.token-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.token-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--p-surface-200);
}

.prefix {
    margin-left: 0.4rem;
    color: var(--p-text-muted-color);
}

.muted {
    color: var(--p-text-muted-color);
    font-size: 0.875rem;
}
</style>
