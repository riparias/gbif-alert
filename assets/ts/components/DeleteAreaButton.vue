<template>
  <button-with-confirmation
      class="btn btn-danger btn-sm gbif-alert-delete-area-button"
      :confirmation-message-body="$t('message.areaDeletionConfirmationMessage')"
      @user-confirmed="userConfirmedDeletion()">
      <i class="bi bi-trash"></i> {{ $t("message.deleteThisArea")}}
  </button-with-confirmation>

  <form method="post" ref="deletionForm" class="d-inline float-end gbif-alert-area-delete-form" :action="props.formAction">
    <input type="hidden" name="csrfmiddlewaretoken" :value="props.csrfToken">
  </form>
</template>

<script setup lang="ts">

import ButtonWithConfirmation from "./ButtonWithConfirmation.vue";
import {ref} from "vue";

const props = defineProps<{
  formAction: string
  csrfToken: string
}>()

const deletionForm = ref(null);

const userConfirmedDeletion = () => {
  (deletionForm.value as unknown as HTMLFormElement).submit();
}

/*
//axios
        .post(
          this.endpointsUrls.markObservationsAsSeenUrl,
          filtersToQuerystring(this.filters),
          { headers: { "X-CSRFToken": (window as any).CSRF_TOKEN } }
        )
*/
</script>