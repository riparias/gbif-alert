<template>
  <button-with-confirmation
      class="btn btn-danger btn-sm riparias-delete-alert-button"
      :button-id="buttonId"
      confirmation-message-body="Do you really want to this alert? This can't be undone."
      @user-confirmed="userConfirmedDeletion()">
      <i class="bi bi-trash"></i> Delete this alert
  </button-with-confirmation>

  <form method="post" ref="form" class="d-inline float-end riparias-alert-delete-form" :action="formAction">
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