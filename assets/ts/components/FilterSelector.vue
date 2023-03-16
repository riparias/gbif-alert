<template>
  <button
    v-bind="$attrs"
    type="button"
    class="btn btn-sm btn-outline-success"
    :class="{
      active: selectionMade,
    }"
    @click="modalActive = true"
  >
    {{ preparedButtonLabel }}
  </button>

  <Filter-Selector-Modal v-if="modalActive"
                         :modal-title="modalTitle"
                         :entries="entries"
                         :label-class="labelClass"
                         v-model="selectedEntriesIds"
                         @clicked-close="modalActive = false">
  </Filter-Selector-Modal>

</template>

<script lang="ts">
import {defineComponent, PropType} from "vue";
import {SelectionEntry} from "../interfaces";
import FilterSelectorModal from "./FilterSelectorModal.vue";

interface ModalMultiSelectorData {
  modalActive: boolean;
  selectedEntriesIds: number[];
}

export default defineComponent({
  name: "FilterSelector",
  components: {FilterSelectorModal},
  props: {
    buttonLabelSingular: { type: String, required: true },
    buttonLabelPlural: { type: String, required: true },
    modalTitle: { type: String, required: true },
    noSelectionButtonLabel: { type: String, required: false },
    labelClass: { type: String, default: "" },
    entries: {
      type: Array as () => SelectionEntry[],
      default: [],
    },
    initiallySelectedEntriesIds: {
      type: Array as PropType<Array<number>>,
      default: [],
    },
  },
  data(): ModalMultiSelectorData {
    return {
      modalActive: false,
      selectedEntriesIds: this.initiallySelectedEntriesIds,
    };
  },
  computed: {
    preparedButtonLabel: function (): string {
      if (!this.selectionMade) {
        // No selection: default label
        if (this.noSelectionButtonLabel) {
          return this.noSelectionButtonLabel;
        } else {
          return "All " + this.buttonLabelPlural;
        }
      } else {
        // 1 single selection: show the value
        if (this.selectedEntriesIds.length === 1 && this.entries.length > 0) {
          return (
            this.buttonLabelSingular +
            ": " +
            this.getEntryPerId(this.selectedEntriesIds[0])!.label
          );
        } else {
          // Multiple selection, return a counter
          return (
            this.selectedEntriesIds.length +
            " selected " +
            this.buttonLabelPlural
          );
        }
      }
    },
    selectionMade: function (): boolean {
      return this.selectedEntriesIds.length >= 1;
    },
  },
  methods: {
    getEntryPerId(id: number): SelectionEntry | undefined {
      return this.entries.find((element) => element.id === id);
    },
  },
  watch: {
    selectedEntriesIds(newVal) {
      this.$emit("entries-changed", newVal);
    },
  },
  emits: ["entries-changed"],
});
</script>
