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
  </div>
</template>

<script setup lang="ts">

import {SelectionEntry} from "@/assets/ts/interfaces";
import {computed} from "vue";
import {v4 as uuidV4} from "uuid";

const uuid = uuidV4();

interface Props {
  entries: SelectionEntry[]
  modelValue: number[]
}

const props = withDefaults(defineProps<Props>(), {
  entries:[],
  modelValue: []
});

const selectedEntriesIds = computed({
  get() {
    return props.modelValue;
  },
  set(newVal) {
    emit('update:modelValue', newVal)
  }
});

const emit = defineEmits(['update:modelValue']);

</script>