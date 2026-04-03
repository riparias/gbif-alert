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
});

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
                    <small v-if="fieldError('delayValue')" style="color: var(--p-red-500);">{{ fieldError("delayValue") }}</small>
                </div>

                <Button :label="t('message.saveProfile')" :loading="saving" class="w-full" @click="save" />

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
