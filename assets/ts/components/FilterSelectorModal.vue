<template>
  <div
      ref="modal"
      class="modal fade show d-block"
      tabindex="-1"
      role="dialog"
      @click="modalClicked($event);"
  >
    <div class="modal-dialog modal-lg" role="document">
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
          <slot></slot>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" @click="emit('clickedClose')"></div>
</template>

<script setup lang="ts">

const props = defineProps<{
  modalTitle: string
}>()

const emit = defineEmits(['clickedClose']);

const modalClicked = (event: Event) => {
  if (event.target === event.currentTarget) {
    // Backdrop was clicked
    emit('clickedClose');
  }
}

</script>