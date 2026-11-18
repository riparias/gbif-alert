<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useToast } from "primevue/usetoast";
import Dialog from "primevue/dialog";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import { getCsrf } from "../utils/csrf";
import type { components } from "../types/api";

type AreaOut = components["schemas"]["AreaOut"];

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{
    "update:visible": [value: boolean];
    created: [area: AreaOut];
}>();

const { t } = useI18n();
const toast = useToast();

const name = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
// Mirrors the native input's selection: its own button and "no file" text are
// rendered in the browser's locale, so we hide it and show translated ones.
const fileName = ref<string | null>(null);
const errorMessage = ref<string | null>(null);
const uploading = ref(false);

function resetForm() {
    name.value = "";
    errorMessage.value = null;
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = "";
    fileName.value = null;
}

function onFileChange() {
    fileName.value = fileInput.value?.files?.[0]?.name ?? null;
}

function onHide() {
    resetForm();
    emit("update:visible", false);
}

async function upload() {
    if (!fileInput.value?.files?.length) return;
    errorMessage.value = null;
    uploading.value = true;

    const formData = new FormData();
    formData.append("name", name.value);
    formData.append("data_file", fileInput.value.files[0]);

    const resp = await fetch("/api/v2/areas/from-file/", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrf(),
        },
        body: formData,
    });

    uploading.value = false;

    if (resp.status === 201) {
        const area: AreaOut = await resp.json();
        toast.add({
            severity: "success",
            summary: t("message.areaCreated"),
            life: 3000,
        });
        emit("created", area);
        resetForm();
    } else {
        const data = await resp.json();
        errorMessage.value = data.detail ?? t("message.unexpectedError");
    }
}
</script>

<template>
    <Dialog
        :visible="props.visible"
        :header="t('message.newArea')"
        :modal="true"
        :style="{ width: '480px', maxWidth: '95vw' }"
        @update:visible="onHide"
    >
        <div style="display: flex; flex-direction: column; gap: 1.25rem; padding: 0.5rem 0">
            <div style="display: flex; flex-direction: column; gap: 0.375rem">
                <label for="area-name" style="display: block; font-weight: 500">
                    {{ t("message.areaName") }}
                </label>
                <InputText id="area-name" v-model="name" class="w-full" />
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.375rem">
                <label for="area-file" style="display: block; font-weight: 500">
                    {{ t("message.areaFile") }}
                </label>
                <input
                    id="area-file"
                    ref="fileInput"
                    type="file"
                    accept=".gpkg"
                    class="visually-hidden"
                    @change="onFileChange"
                />
                <div style="display: flex; align-items: center; gap: 0.75rem">
                    <Button
                        :label="t('message.chooseFile')"
                        icon="pi pi-upload"
                        severity="secondary"
                        size="small"
                        @click="fileInput?.click()"
                    />
                    <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
                        {{ fileName ?? t("message.noFileChosen") }}
                    </span>
                </div>
                <small style="color: var(--p-text-muted-color, #6b7280)">{{
                    t("message.areaFileHint")
                }}</small>
            </div>

            <Message v-if="errorMessage" severity="error" data-testid="area-upload-error">
                {{ errorMessage }}
            </Message>
        </div>

        <template #footer>
            <Button :label="t('message.cancel')" severity="secondary" @click="onHide" />
            <Button
                :label="t('message.upload')"
                :loading="uploading"
                :disabled="!name || !fileName || uploading"
                @click="upload"
            />
        </template>
    </Dialog>
</template>

<style scoped>
/* Visually hidden but still focusable/clickable, so the label and tests still reach it. */
.visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
}
</style>
