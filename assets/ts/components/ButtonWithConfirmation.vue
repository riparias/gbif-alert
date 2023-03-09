<template>
  <button :id="buttonId" :class="$attrs.class" @click="confirmationModalOpen = true">
    <slot></slot>
  </button>

  <confirmation-modal
      :modal-open="confirmationModalOpen"
      :confirmation-message-title="confirmationMessageTitle"
      :confirmation-message-body="confirmationMessageBody"
      @click-yes="clickYes()"
      @click-no="clickNo()"
  ></confirmation-modal>
</template>

<script lang="ts">
import {defineComponent, ref} from "vue";
import ConfirmationModal from "./ConfirmationModal.vue";

export default defineComponent({
  name: "ButtonWithConfirmation",
  emits: ["user-confirmed"],
  components: {ConfirmationModal},
  props: {
    buttonId: {
      type: String,
      required: true,
    },
    confirmationMessageTitle: {
      type: String,
      required: false,
    },
    confirmationMessageBody: {
      type: String,
      required: false,
    },
  },
  setup(props, context) {
    const confirmationModalOpen = ref(false);

    const clickYes = function () {
      context.emit("user-confirmed");
      confirmationModalOpen.value = false;
    }

    const clickNo = function () {
      confirmationModalOpen.value = false;
    }

    return {confirmationModalOpen, clickYes, clickNo};
  }
});
</script>