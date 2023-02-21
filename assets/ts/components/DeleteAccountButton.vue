<template>
  <button-with-confirmation
      class="btn btn-danger float-end"
      :button-id="buttonId"
      button-label="Delete my account"
      confirmation-message-body="Do you really want to delete your account? This can't be undone, and all your data (alerts, observation comments, ...) will be lost!"
      @user-confirmed="userConfirmedDeletion()">
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