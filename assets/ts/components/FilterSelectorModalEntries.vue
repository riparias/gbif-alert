<template>
    <div v-for="entry in props.entries" class="form-check">
        <input
                class="form-check-input"
                type="checkbox"
                :value="entry.id"
                :id="'pterois-mms-entry-' + uuid + '-' + entry.id"
                v-model="selectedEntriesIds"
        />
        <label
                class="form-check-label"
                :for="'pterois-mms-entry-' + uuid + '-' + entry.id"
        >
            {{ entry.label }}
        </label>

        <span v-for="tag in entry.tags"
              :style="getStyleForTag(tag)"
              class="badge bg-secondary mx-1"
        >
          {{ tag }}
        </span>
    </div>
</template>

<script setup lang="ts">

import {SelectionEntry} from "../interfaces";
import {ref, watch} from "vue";
import {v4 as uuidV4} from "uuid";
import {getStyleForTag} from "../helpers";

const uuid = uuidV4();

interface Props {
    entries: SelectionEntry[]
    modelValue: number[]
}

const props = withDefaults(defineProps<Props>(), {
    entries: [],
    modelValue: []
});

const selectedEntriesIds = ref<number[]>(props.modelValue);

const emit = defineEmits(['update:modelValue']);

watch(selectedEntriesIds, (newVal) => {
    emit('update:modelValue', newVal)
})
</script>