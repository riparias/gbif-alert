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
          <Filter-Selector-Modal-Entries
              :entries="props.entries"
              :label-class="props.labelClass"
              v-model="selectedEntriesIds"
          >
          </Filter-Selector-Modal-Entries>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" @click="emit('clickedClose')"></div>
</template>

<script setup lang="ts">
import {SelectionEntry} from "../interfaces";
import {ref, watch} from "vue";
import FilterSelectorModalEntries from "./FilterSelectorModalEntries.vue";

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