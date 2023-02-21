<template>
  <button :id="buttonId" :class="$attrs.class" @click="confirmationModalOpen = true">
    {{ buttonLabel }}
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
import {defineComponent} from "vue";
import ConfirmationModal from "./ConfirmationModal.vue";

export default defineComponent({
  name: "ButtonWithConfirmation",
  emits: ["user-confirmed"],
  components: {ConfirmationModal},
  props: {
    buttonLabel: {
      type: String,
      required: true,
    },
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
  data: function () {
    return {
      confirmationModalOpen: false,
    };
  },
  methods: {
    clickYes: function () {
      this.$emit("user-confirmed");
      this.confirmationModalOpen = false;
    },
    clickNo: function () {
      this.confirmationModalOpen = false;
    },
  },
});
</script>