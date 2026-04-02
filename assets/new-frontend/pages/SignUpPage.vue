<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import { getCsrf } from "../utils/csrf";

const { t } = useI18n();

const username = ref("");
const firstName = ref("");
const lastName = ref("");
const email = ref("");
const language = ref((window as any).LANGUAGE_CODE ?? "en");
const password1 = ref("");
const password2 = ref("");
const fieldErrors = ref<Record<string, string[]>>({});
const loading = ref(false);

function fieldError(field: string): string | null {
    return fieldErrors.value[field]?.[0] ?? null;
}

async function submit() {
    fieldErrors.value = {};
    loading.value = true;
    const resp = await fetch("/api/v2/auth/signup/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
        },
        body: JSON.stringify({
            username: username.value,
            first_name: firstName.value,
            last_name: lastName.value,
            email: email.value,
            language: language.value,
            password1: password1.value,
            password2: password2.value,
        }),
    });
    loading.value = false;
    if (resp.status === 201) {
        window.location.href = "/";
    } else {
        const data = await resp.json();
        fieldErrors.value = data.errors ?? {};
    }
}
</script>

<template>
    <div style="max-width: 420px; margin: 4rem auto; padding: 0 1rem;">
        <h1 style="margin-bottom: 1.5rem;">{{ t("message.signUp") }}</h1>

        <div style="display: flex; flex-direction: column; gap: 1rem;">
            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="su-username" style="font-weight: 500;">{{ t("message.username") }} <span style="font-weight: 400; color: var(--p-text-muted-color);">*</span></label>
                <InputText id="su-username" v-model="username" class="w-full" autocomplete="username" />
                <small v-if="fieldError('username')" style="color: var(--p-red-500);">{{ fieldError("username") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="su-email" style="font-weight: 500;">{{ t("message.email") }} <span style="font-weight: 400; color: var(--p-text-muted-color);">*</span></label>
                <InputText id="su-email" v-model="email" type="email" class="w-full" autocomplete="email" />
                <small v-if="fieldError('email')" style="color: var(--p-red-500);">{{ fieldError("email") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="su-firstname" style="font-weight: 500;">
                    {{ t("message.firstName") }}
                    <span style="font-weight: 400; color: var(--p-text-muted-color);">({{ t("message.optional") }})</span>
                </label>
                <InputText id="su-firstname" v-model="firstName" class="w-full" autocomplete="given-name" />
                <small v-if="fieldError('first_name')" style="color: var(--p-red-500);">{{ fieldError("first_name") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="su-lastname" style="font-weight: 500;">
                    {{ t("message.lastName") }}
                    <span style="font-weight: 400; color: var(--p-text-muted-color);">({{ t("message.optional") }})</span>
                </label>
                <InputText id="su-lastname" v-model="lastName" class="w-full" autocomplete="family-name" />
                <small v-if="fieldError('last_name')" style="color: var(--p-red-500);">{{ fieldError("last_name") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="su-password1" style="font-weight: 500;">{{ t("message.newPassword") }} <span style="font-weight: 400; color: var(--p-text-muted-color);">*</span></label>
                <InputText id="su-password1" v-model="password1" type="password" class="w-full" autocomplete="new-password" />
                <small v-if="fieldError('password1')" style="color: var(--p-red-500);">{{ fieldError("password1") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="su-password2" style="font-weight: 500;">{{ t("message.confirmNewPassword") }} <span style="font-weight: 400; color: var(--p-text-muted-color);">*</span></label>
                <InputText id="su-password2" v-model="password2" type="password" class="w-full" autocomplete="new-password" @keyup.enter="submit" />
                <small v-if="fieldError('password2')" style="color: var(--p-red-500);">{{ fieldError("password2") }}</small>
            </div>

            <Message v-if="fieldError('__all__')" severity="error">{{ fieldError("__all__") }}</Message>

            <Button :label="t('message.signUp')" :loading="loading" class="w-full" @click="submit" />
        </div>

        <div style="margin-top: 1rem;">
            {{ t("message.alreadyHaveAccount") }}
            <a href="/accounts/signin/">{{ t("message.signIn") }}</a>
        </div>
    </div>
</template>
