<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import { getCsrf } from "../utils/csrf";
import { getNavConfig } from "../utils/navConfig";

const { t } = useI18n();
const router = useRouter();
const toast = useToast();

const isAuthenticated = getNavConfig().user?.isAuthenticated ?? false;

onMounted(() => {
    if (!isAuthenticated) {
        router.push("/accounts/signin/");
    }
});

const oldPassword = ref("");
const newPassword1 = ref("");
const newPassword2 = ref("");
const fieldErrors = ref<Record<string, string[]>>({});
const loading = ref(false);

function fieldError(field: string): string | null {
    return fieldErrors.value[field]?.[0] ?? null;
}

async function submit() {
    fieldErrors.value = {};
    loading.value = true;
    const resp = await fetch("/api/v2/auth/password-change/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrf(),
        },
        body: JSON.stringify({
            oldPassword: oldPassword.value,
            newPassword1: newPassword1.value,
            newPassword2: newPassword2.value,
        }),
    });
    loading.value = false;
    if (resp.status === 204) {
        toast.add({ severity: "success", summary: t("message.passwordChanged"), life: 3000 });
        router.push("/profile");
    } else {
        const data = await resp.json();
        fieldErrors.value = data.errors ?? {};
    }
}
</script>

<template>
    <div class="page-content--narrow password-change-page">
        <h1 style="margin-bottom: 1.5rem;">{{ t("message.changePassword") }}</h1>

        <div style="display: flex; flex-direction: column; gap: 1rem;">
            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="cp-old" style="font-weight: 500;">{{ t("message.oldPassword") }}</label>
                <InputText id="cp-old" v-model="oldPassword" type="password" class="w-full" autocomplete="current-password" />
                <small v-if="fieldError('oldPassword')" style="color: var(--p-red-500);">{{ fieldError("oldPassword") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="cp-new1" style="font-weight: 500;">{{ t("message.newPassword") }}</label>
                <InputText id="cp-new1" v-model="newPassword1" type="password" class="w-full" autocomplete="new-password" />
                <small v-if="fieldError('newPassword1')" style="color: var(--p-red-500);">{{ fieldError("newPassword1") }}</small>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem;">
                <label for="cp-new2" style="font-weight: 500;">{{ t("message.confirmNewPassword") }}</label>
                <InputText id="cp-new2" v-model="newPassword2" type="password" class="w-full" autocomplete="new-password" @keyup.enter="submit" />
                <small v-if="fieldError('newPassword2')" style="color: var(--p-red-500);">{{ fieldError("newPassword2") }}</small>
            </div>

            <Button :label="t('message.changePassword')" :loading="loading" class="w-full" @click="submit" />
        </div>
    </div>
</template>

<style scoped>
.password-change-page { margin-top: 4rem; }
</style>
