<template>
  <div
    class="modal fade"
    :class="{ show: modalOpen, 'd-block': modalOpen }"
    tabindex="-1"
    role="dialog"
  >
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ confirmationMessageTitleComputed }}</h5>
        </div>
        <div class="modal-body">
          <p>{{ confirmationMessageBodyComputed }}</p>
        </div>
        <div class="modal-footer">
          <button
            id="modal-button-yes"
            type="button"
            class="btn btn-danger btn-sm"
            @click="$emit('click-yes')"
          >
              {{ $t("message.yesImSure") }}
          </button>
          <button
            id="modal-button-no"
            type="button"
            class="btn btn-secondary btn-sm"
            @click="$emit('click-no')"
          >
            {{ $t("message.cancel") }}
          </button>
        </div>
      </div>
    </div>
  </div>
  <div v-if="modalOpen" class="modal-backdrop fade show"></div>
</template>

<script lang="ts">
import {defineComponent} from "vue";

export default defineComponent({
  name: "ConfirmationModal",
  props: {
    modalOpen: {
      type: Boolean,
      default: false,
    },
    confirmationMessageTitle: {
      type: String,
      required: false
    },
    confirmationMessageBody: {
      type: String,
      required: false
    },
  },
  emits: ["click-yes", "click-no"],
  computed: {
      confirmationMessageTitleComputed: function () {
          return this.confirmationMessageTitle || this.$t("message.areYouSure");
      },
      confirmationMessageBodyComputed: function () {
          return this.confirmationMessageBody || this.$t("message.thisOperationCantBeUndone");
      }
  },
});
</script>
