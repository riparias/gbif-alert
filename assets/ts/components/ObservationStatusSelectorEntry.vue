<template>
  <input
    type="radio"
    class="btn-check"
    name="btnradio"
    :id="elementId"
    autocomplete="off"
    :checked="checked"
    @click="$emit('entrySelected')"
  />
  <label class="btn btn-outline-primary" :for="elementId">{{
    entryLabel
  }}</label>
</template>

<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "ObservationStatusSelectorEntry",
  props: {
    entryLabel: {
      type: String,
      required: true,
    },
    checked: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    elementId: function (): string {
      return "btnRadio" + this.entryLabel;
    },
  },
  emits: ["entrySelected"],
});
</script>
