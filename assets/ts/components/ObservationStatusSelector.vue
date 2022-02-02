<template>
  Status:
  <div
    class="btn-group btn-group-sm"
    role="group"
    aria-label="Basic radio toggle button group"
  >
    <ObservationStatusSelectorEntry
      entry-label="All"
      :checked="modelValue === null"
      @entry-selected="myEmit(null)"
    ></ObservationStatusSelectorEntry>
    <ObservationStatusSelectorEntry
      entry-label="Seen"
      :checked="modelValue === 'seen'"
      @entry-selected="myEmit('seen')"
    ></ObservationStatusSelectorEntry>
    <ObservationStatusSelectorEntry
      entry-label="Unseen"
      :checked="modelValue === 'unseen'"
      @entry-selected="myEmit('unseen')"
    ></ObservationStatusSelectorEntry>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import ObservationStatusSelectorEntry from "./ObservationStatusSelectorEntry.vue";

export default defineComponent({
  name: "ObservationStatusSelector",
  components: { ObservationStatusSelectorEntry },
  props: ["modelValue"],
  emits: ["update:modelValue"],
  methods: {
    myEmit: function (v: string | null) {
      console.log("Passe myEmit, value", v);
      this.$emit("update:modelValue", v);
    },
  },
});
</script>
