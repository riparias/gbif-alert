<template>
  <button
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
import { defineComponent } from "vue";
import { SelectionEntry } from "../interfaces";
import { v4 as uuidv4 } from "uuid";

export default defineComponent({
  name: "ModalMultiSelector",
  props: {
    buttonLabel: { type: String, required: true },
    modalTitle: { type: String, required: true },
    entries: {
      type: Array as () => SelectionEntry[],
      default: [],
    },
  },
  data() {
    return {
      modalActive: false,
      selectedEntriesIds: [],
      uuid: uuidv4(),
    };
  },
  computed: {
    preparedButtonLabel: function (): string {
      if (!this.selectionMade) {
        // No selection: default label
        return this.buttonLabel;
      } else {
        // 1 single selection: show the value
        if (this.selectedEntriesIds.length === 1) {
          return this.getEntryPerId(this.selectedEntriesIds[0])!.label;
        } else {
          // Multiple selection, return a counter
          return this.selectedEntriesIds.length + " selected species";
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
});
</script>
