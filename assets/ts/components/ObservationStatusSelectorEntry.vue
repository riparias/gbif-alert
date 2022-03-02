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
  <label
    class="btn btn-outline-success"
    :for="elementId"
    :id="`label-${elementId}`"
  >
    {{ entryLabel }}
    <span v-if="count" class="badge bg-dark">{{ formattedCount }}</span>
  </label>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { formatCount } from "../helpers";

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
    count: {
      type: Number,
      required: false,
    },
  },
  computed: {
    formattedCount: function (): string | undefined {
      if (this.count) {
        return formatCount(this.count);
      }
    },
    elementId: function (): string {
      return "btnRadio" + this.entryLabel;
    },
  },
  emits: ["entrySelected"],
});
</script>
