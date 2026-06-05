<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import { useConfirm } from "primevue/useconfirm";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
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
const enabledLanguages = getNavConfig().enabledLanguages ?? [{ code: "en", nameLocal: "English" }];

onMounted(async () => {
    if (!isAuthenticated) {
        router.push("/accounts/signin/");
        return;
    }
    await loadProfile();
    await loadTokens();
});

// --- API tokens ---

const tokens = ref<ApiTokenOut[]>([]);
const newTokenName = ref("");
const creatingToken = ref(false);
// The raw value of a just-created token, shown once.
const createdToken = ref<string | null>(null);

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

async function copyCreatedToken() {
    if (createdToken.value) {
        await navigator.clipboard?.writeText(createdToken.value).catch(() => {});
        toast.add({ severity: "success", summary: t("message.apiTokenCopied"), life: 2000 });
    }
}

function formatDate(iso: string | null): string {
    return iso ? new Date(iso).toLocaleDateString() : t("message.never");
}

const loading = ref(true);
const saving = ref(false);
const fieldErrors = ref<Record<string, string[]>>({});

const username = ref("");
const firstName = ref("");
const lastName = ref("");
const email = ref("");
const language = ref("en");
const delayValue = ref(1);
const delayUnit = ref("years");

const languageOptions = computed(() =>
    enabledLanguages.map((lang) => ({ value: lang.code, label: lang.nameLocal }))
);

const delayUnitOptions = computed(() => [
    { value: "days", label: t("message.days") },
    { value: "weeks", label: t("message.weeks") },
    { value: "months", label: t("message.months") },
    { value: "years", label: t("message.years") },
]);

function fieldError(field: string): string | null {
    return fieldErrors.value[field]?.[0] ?? null;
}

async function loadProfile() {
    loading.value = true;
    const resp = await fetch("/api/v2/profile/");
    if (resp.ok) {
        const data = await resp.json();
        username.value = data.username;
        firstName.value = data.firstName;
        lastName.value = data.lastName;
        email.value = data.email;
        language.value = data.language;
        delayValue.value = data.delayValue;
        delayUnit.value = data.delayUnit;
    }
    loading.value = false;
}

async function save() {
    fieldErrors.value = {};
    saving.value = true;
    const resp = await fetch("/api/v2/profile/", {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
        },
        body: JSON.stringify({
            firstName: firstName.value,
            lastName: lastName.value,
            email: email.value,
            language: language.value,
            delayValue: delayValue.value,
            delayUnit: delayUnit.value,
        }),
    });
    saving.value = false;
    if (resp.ok) {
        const data = await resp.json();
        delayValue.value = data.delayValue;
        delayUnit.value = data.delayUnit;
        toast.add({ severity: "success", summary: t("message.profileSaved"), life: 3000 });
    } else {
        const data = await resp.json();
        fieldErrors.value = data.errors ?? {};
    }
}

function requestDeleteAccount() {
    confirm.require({
        message: t("message.confirmDeleteAccount"),
        header: t("message.confirmDeleteAccountHeader"),
        icon: "pi pi-exclamation-triangle",
        acceptLabel: t("message.yesImSure"),
        rejectLabel: t("message.cancel"),
        accept: deleteAccount,
    });
}

async function deleteAccount() {
    const resp = await fetch("/api/v2/account/", {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrf() },
    });
    if (resp.status === 204) {
        window.location.href = "/accounts/signin/";
    }
}
</script>

<template>
    <div class="page-content--narrow">
        <h1 style="margin-bottom: 1.5rem;">{{ t("message.navMyProfile") }}</h1>

        <ProgressSpinner v-if="loading" />

        <template v-else>
            <div style="display: flex; flex-direction: column; gap: 1rem;">
                <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                    <label style="font-weight: 500;">{{ t("message.username") }}</label>
                    <InputText :value="username" disabled class="w-full" />
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                    <label for="p-firstname" style="font-weight: 500;">{{ t("message.firstName") }}</label>
                    <InputText id="p-firstname" v-model="firstName" class="w-full" />
                    <small v-if="fieldError('firstName')" style="color: var(--p-red-500);">{{ fieldError("firstName") }}</small>
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                    <label for="p-lastname" style="font-weight: 500;">{{ t("message.lastName") }}</label>
                    <InputText id="p-lastname" v-model="lastName" class="w-full" />
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                    <label for="p-email" style="font-weight: 500;">{{ t("message.email") }}</label>
                    <InputText id="p-email" v-model="email" type="email" class="w-full" />
                    <small v-if="fieldError('email')" style="color: var(--p-red-500);">{{ fieldError("email") }}</small>
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                    <label for="p-language" style="font-weight: 500;">{{ t("message.language") }}</label>
                    <Select
                        id="p-language"
                        v-model="language"
                        :options="languageOptions"
                        option-label="label"
                        option-value="value"
                        class="w-full"
                    />
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                    <label style="font-weight: 500;">{{ t("message.notificationDelay") }}</label>
                    <div style="display: flex; gap: 0.5rem;">
                        <InputText
                            v-model.number="delayValue"
                            type="number"
                            min="1"
                            style="width: 80px;"
                        />
                        <Select
                            v-model="delayUnit"
                            :options="delayUnitOptions"
                            option-label="label"
                            option-value="value"
                            style="flex: 1;"
                        />
                    </div>
                    <small style="color: var(--p-text-muted-color);">{{ t("message.notificationDelayHelp") }}</small>
                    <small v-if="fieldError('delayValue')" style="color: var(--p-red-500);">{{ fieldError("delayValue") }}</small>
                </div>

                <Button :label="t('message.saveProfile')" :loading="saving" class="w-full" @click="save" />

                <hr style="margin: 1rem 0; border: none; border-top: 1px solid var(--p-surface-200);" />

                <!-- API tokens -->
                <section class="api-tokens">
                    <h2 style="font-size: 1.1rem; margin-bottom: 0.25rem;">{{ t("message.apiTokensTitle") }}</h2>
                    <p style="color: var(--p-text-muted-color); font-size: 0.875rem; margin-bottom: 0.75rem;">
                        {{ t("message.apiTokensIntro") }}
                    </p>

                    <!-- Just-created token, shown once -->
                    <div v-if="createdToken" class="created-token">
                        <small style="color: var(--p-orange-600); font-weight: 500;">{{ t("message.apiTokenCreatedWarning") }}</small>
                        <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                            <InputText :value="createdToken" readonly class="w-full" data-testid="created-token-value" />
                            <Button icon="pi pi-copy" :label="t('message.copy')" size="small" @click="copyCreatedToken" />
                        </div>
                    </div>

                    <!-- Existing tokens -->
                    <ul v-if="tokens.length" class="token-list">
                        <li v-for="tk in tokens" :key="tk.id" class="token-row">
                            <div>
                                <span style="font-weight: 500;">{{ tk.name || tk.prefix }}</span>
                                <code style="margin-left: 0.4rem; color: var(--p-text-muted-color);">{{ tk.prefix }}&hellip;</code>
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
                    <p v-else style="color: var(--p-text-muted-color); font-size: 0.875rem;">{{ t("message.noApiTokens") }}</p>

                    <!-- Create -->
                    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
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
                </section>

                <hr style="margin: 1rem 0; border: none; border-top: 1px solid var(--p-surface-200);" />

                <Button
                    :label="t('message.deleteAccount')"
                    severity="danger"
                    outlined
                    class="w-full"
                    data-testid="delete-account-btn"
                    @click="requestDeleteAccount"
                />
            </div>
        </template>
    </div>
</template>
