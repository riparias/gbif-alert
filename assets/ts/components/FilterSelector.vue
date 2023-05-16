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
                         @clicked-close="modalActive = false">

    <SpeciesSelector v-if="speciesMode" :available-species="entries" v-model="selectedEntriesIds"  />
    <Filter-Selector-Modal-Entries v-else :entries="entries" v-model="selectedEntriesIds" />

      <!-- Let's pass a slot from parent directly to children... -->
      <template v-slot:body-top>
          <slot name="modal-body-top"></slot>
      </template>
  </Filter-Selector-Modal>

</template>

<script lang="ts">
import {defineComponent, PropType} from "vue";
import {SelectionEntry, SpeciesInformationWithLabel} from "../interfaces";
import FilterSelectorModal from "./FilterSelectorModal.vue";
import FilterSelectorModalEntries from "./FilterSelectorModalEntries.vue";
import SpeciesSelector from "./SpeciesSelector.vue";

interface ModalMultiSelectorData {
  modalActive: boolean;
  selectedEntriesIds: number[];
}

export default defineComponent({
  name: "FilterSelector",
  components: {SpeciesSelector, FilterSelectorModal, FilterSelectorModalEntries},
  props: {
    // Is species mode:
    //  - a different component is used as the modal body
    //  - entries type should be SpeciesInformation[] instead of SelectionEntry[]
    speciesMode: { type: Boolean, required: false, default: false },
    buttonLabelSingular: { type: String, required: true },
    buttonLabelSuffixPlural: { type: String, required: true },
    modalTitle: { type: String, required: true },
    noSelectionButtonLabel: { type: String, required: true },
    entries: {
      type: Array as () => SelectionEntry[] | SpeciesInformationWithLabel[],
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
          return this.noSelectionButtonLabel;
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
            this.selectedEntriesIds.length + " " + this.buttonLabelSuffixPlural
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
