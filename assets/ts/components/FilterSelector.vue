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

    <Selector
        :available-entries="entries"
        v-model="selectedEntriesIds"
        :columns-config="selectorColumnsConfig"
        :initial-sort-by="selectorInitialSortBy"
        :initial-sort-direction="selectorInitialSortDirection"
    >
    </Selector>
  </Filter-Selector-Modal>

</template>

<script lang="ts">
import {defineComponent, PropType} from "vue";
import {ColumnMetadata, DataRow} from "../interfaces";
import FilterSelectorModal from "./FilterSelectorModal.vue";
import Selector from "./Selector.vue";

interface ModalMultiSelectorData {
  modalActive: boolean;
  selectedEntriesIds: number[];
}

export default defineComponent({
  name: "FilterSelector",
  components: {Selector, FilterSelectorModal},
  props: {
    buttonLabelSingular: {type: String, required: true},
    buttonLabelSuffixPlural: {type: String, required: true},
    modalTitle: {type: String, required: true},
    noSelectionButtonLabel: {type: String, required: true},
    entries: {
      type: Array as () => DataRow[],
      default: [],
    },
    labelIndex: {  // Index of the entry (in entries[x].columnData) that should be used as the button label (single selection)
      type: Number,
      required: false,
      default: 0,
    },
    selectorColumnsConfig: {
      type: Array as () => ColumnMetadata[],
    },
    selectorInitialSortBy: {
      type: Number,
      required: false,
      default: 0,
    },
    selectorInitialSortDirection: {
      type: String,
      required: false,
      default: "asc",
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
              this.getDataRowPerId(this.selectedEntriesIds[0])!.columnData[this.labelIndex]
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
    getDataRowPerId(id: number): DataRow | undefined {
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
