<template>
  <button-with-confirmation
      class="btn btn-danger btn-sm float-end"
      :button-id="buttonId"
      :confirmation-message-body="$t('message.accountDeletionConfirmationMessage')"
      @user-confirmed="userConfirmedDeletion()">
      <i class="bi bi-trash"></i> {{ $t("message.deleteMyAccount")}}
  </button-with-confirmation>

  <form method="post" ref="form" :action="formAction">
    <slot></slot>
  </form>

</template>

<script lang="ts">
import {defineComponent} from "vue";
import ButtonWithConfirmation from "./ButtonWithConfirmation.vue";

export default defineComponent({
  name: "DeleteAccountButton",
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