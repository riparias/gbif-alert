<template>
  <button-with-confirmation
      class="btn btn-danger btn-sm pterois-delete-alert-button"
      :button-id="buttonId"
      :confirmation-message-body="$t('message.alertDeletionConfirmationMessage')"
      @user-confirmed="userConfirmedDeletion()">
      <i class="bi bi-trash"></i> {{ $t("message.deleteThisAlert")}}
  </button-with-confirmation>

  <form method="post" ref="form" class="d-inline float-end pterois-alert-delete-form" :action="formAction">
    <slot></slot>
  </form>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import ButtonWithConfirmation from "./ButtonWithConfirmation.vue";

export default defineComponent({
  name: "DeleteAlertButton",
  props: {
    formAction: {
      type: String,
      required: true,
    },
    buttonId: {
      type: String,
      required: true,
    },
  },
  components: {ButtonWithConfirmation},
  methods: {
    userConfirmedDeletion: function () {
      (this.$refs.form as any).submit();
    },
  },
});
</script>