<template>
  <button :id="props.buttonId" :class="$attrs.class" @click="confirmationModalOpen = true">
    <slot></slot>
  </button>

  <confirmation-modal
      :modal-open="confirmationModalOpen"
      :confirmation-message-title="props.confirmationMessageTitle"
      :confirmation-message-body="props.confirmationMessageBody"
      @click-yes="clickYes()"
      @click-no="clickNo()"
  ></confirmation-modal>
</template>

<script setup lang="ts">
import {ref} from "vue";
import ConfirmationModal from "./ConfirmationModal.vue";

const props = defineProps<{
  buttonId: string
  confirmationMessageTitle?: string
  confirmationMessageBody?: string
}>()

const confirmationModalOpen = ref(false);

const emit = defineEmits(["user-confirmed"]);

const clickYes = function () {
  emit("user-confirmed");
  confirmationModalOpen.value = false;
}

const clickNo = function () {
  confirmationModalOpen.value = false;
}
</script>