<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { tagColor } from "../utils/tagColor";

// Tag chips for the picker modals. Active tags only narrow the modal's list;
// the hint says so, because users read the chips as a filter that selects (#470).
const props = defineProps<{
    modelValue: string[];
    tags: string[];
}>();

const emit = defineEmits<{
    "update:modelValue": [tags: string[]];
}>();

const { t } = useI18n();

function toggleTag(tag: string) {
    emit(
        "update:modelValue",
        props.modelValue.includes(tag)
            ? props.modelValue.filter((x) => x !== tag)
            : [...props.modelValue, tag],
    );
}
</script>

<template>
    <div v-if="tags.length" class="tag-filter-row">
        <span class="tag-filter-label">{{ t("message.filterByTags") }}</span>
        <div class="tag-chips">
            <span
                v-for="tag in tags"
                :key="tag"
                class="tag-chip"
                :class="{ 'tag-chip--active': modelValue.includes(tag) }"
                :style="
                    modelValue.includes(tag)
                        ? {
                              backgroundColor: tagColor(tag),
                              color: '#fff',
                              borderColor: tagColor(tag),
                          }
                        : { borderColor: tagColor(tag), color: tagColor(tag) }
                "
                @click="toggleTag(tag)"
                >{{ tag }}</span
            >
        </div>
        <small class="tag-filter-hint">{{ t("message.filterByTagsHint") }}</small>
    </div>
</template>

<style scoped>
.tag-filter-row {
    margin-bottom: 0.75rem;
}

.tag-filter-label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--p-text-muted-color);
    margin-bottom: 0.4rem;
}

.tag-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.tag-chip {
    cursor: pointer;
    padding: 2px 9px;
    border-radius: 10px;
    border: 1px solid;
    font-size: 0.78rem;
    white-space: nowrap;
    user-select: none;
    transition:
        background-color 0.15s,
        color 0.15s;
}

.tag-chip--active {
    font-weight: 600;
}

.tag-filter-hint {
    display: block;
    margin-top: 0.4rem;
    color: var(--p-text-muted-color);
}
</style>
