<template>
  <div
      ref="modal"
      class="modal fade show d-block"
      tabindex="-1"
      role="dialog"
      @click="modalClicked($event);"
  >
    <div class="modal-dialog" role="document">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ props.modalTitle }}</h5>
          <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
              @click="emit('clickedClose')"
          ></button>
        </div>
        <div class="modal-body">
          <div v-for="entry in props.entries" class="form-check">
            <input
                class="form-check-input"
                type="checkbox"
                :value="entry.id"
                :id="'mms-entry-' + uuid + '-' + entry.id"
                v-model="selectedEntriesIds"
            />
            <label
                class="form-check-label"
                :class="props.labelClass"
                :for="'mms-entry-' + uuid + '-' + entry.id"
            >
              {{ entry.label }}
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" @click="emit('clickedClose')"></div>
</template>

<script setup lang="ts">
import {v4 as uuidV4} from "uuid";
import {SelectionEntry} from "../interfaces";
import {ref, watch} from "vue";

const uuid = uuidV4();

interface Props {
  modalTitle: string,
  entries: SelectionEntry[]
  labelClass?: string
  modelValue: number[]
}

const props = withDefaults(defineProps<Props>(), {
  //modalTitle: "",
  entries:[],
  labelClass: "",
  modelValue: []
});

const selectedEntriesIds = ref<number[]>(props.modelValue);

const emit = defineEmits(['clickedClose', 'update:modelValue']);

const modalClicked = (event: Event) => {
  if (event.target === event.currentTarget) {
    // Backdrop was clicked
    emit('clickedClose');
  }
}

watch(selectedEntriesIds, (newVal) => {
  emit('update:modelValue', newVal)
})
</script>