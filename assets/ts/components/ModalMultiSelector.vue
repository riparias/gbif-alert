<template>
  <button
    v-bind="$attrs"
    type="button"
    class="btn btn-sm btn-outline-success"
    :class="{
      active: selectionMade,
    }"
    @click="modalToggle"
  >
    {{ preparedButtonLabel }}
  </button>

  <div
    ref="modal"
    class="modal fade"
    :class="{ show: modalActive, 'd-block': modalActive }"
    tabindex="-1"
    role="dialog"
  >
    <div class="modal-dialog" role="document">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ modalTitle }}</h5>
          <button
            type="button"
            class="btn-close"
            data-bs-dismiss="modal"
            aria-label="Close"
            @click="modalToggle"
          ></button>
        </div>
        <div class="modal-body">
          <div v-for="entry in entries" class="form-check">
            <input
              class="form-check-input"
              type="checkbox"
              :value="entry.id"
              :id="'mms-entry-' + uuid + '-' + entry.id"
              v-model="selectedEntriesIds"
            />
            <label
              class="form-check-label"
              :for="'mms-entry-' + uuid + '-' + entry.id"
            >
              {{ entry.label }}
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-if="modalActive" class="modal-backdrop fade show"></div>
</template>

<script lang="ts">
import { defineComponent, PropType } from "vue";
import { SelectionEntry } from "../interfaces";
import { v4 as uuidv4 } from "uuid";

interface ModalMultiSelectorData {
  modalActive: boolean;
  selectedEntriesIds: number[];
  uuid: string;
}

export default defineComponent({
  name: "ModalMultiSelector",
  props: {
    buttonLabelSingular: { type: String, required: true },
    buttonLabelPlural: { type: String, required: true },
    modalTitle: { type: String, required: true },
    noSelectionButtonLabel: { type: String, required: false },
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
      uuid: uuidv4(),
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
    modalToggle() {
      const body = document.querySelector("body");
      this.modalActive = !this.modalActive;
      this.modalActive
        ? body!.classList.add("modal-open")
        : body!.classList.remove("modal-open");
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
