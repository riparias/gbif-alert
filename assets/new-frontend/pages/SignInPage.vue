<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import { getCsrf } from "../utils/csrf";

const { t } = useI18n();

const username = ref("");
const password = ref("");
const errorMessage = ref<string | null>(null);
const loading = ref(false);

async function submit() {
    errorMessage.value = null;
    loading.value = true;
    const resp = await fetch("/api/v2/auth/signin/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
        },
        body: JSON.stringify({ username: username.value, password: password.value }),
    });
    loading.value = false;
    if (resp.ok) {
        window.location.href = "/";
    } else {
        const data = await resp.json();
        errorMessage.value = t("message.invalidCredentials");
    }
}
</script>

<template>
    <div class="page-content--narrow signin-page">
        <h1 style="margin-bottom: 1.5rem;">{{ t("message.signIn") }}</h1>

        <div style="display: flex; flex-direction: column; gap: 1rem;">
            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="signin-username" style="font-weight: 500;">{{ t("message.username") }}</label>
                <InputText
                    id="signin-username"
                    v-model="username"
                    class="w-full"
                    autocomplete="username"
                />
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="signin-password" style="font-weight: 500;">{{ t("message.password") }}</label>
                <InputText
                    id="signin-password"
                    v-model="password"
                    type="password"
                    class="w-full"
                    autocomplete="current-password"
                    @keyup.enter="submit"
                />
            </div>

            <Message v-if="errorMessage" severity="error" data-testid="signin-error">
                {{ errorMessage }}
            </Message>

            <Button
                :label="t('message.signIn')"
                :loading="loading"
                class="w-full"
                @click="submit"
            />
        </div>

        <div style="margin-top: 1rem; display: flex; flex-direction: column; gap: 0.5rem;">
            <a href="/accounts/password-reset/">{{ t("message.forgotPassword") }}</a>
            <span>
                {{ t("message.noAccountYet") }}
                <a href="/signup">{{ t("message.signUp") }}</a>
            </span>
        </div>
    </div>
</template>

<style scoped>
.signin-page { margin-top: 4rem; }
</style>
