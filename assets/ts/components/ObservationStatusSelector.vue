<template>
  <div class="small d-inline-block mx-3">
    Status:
    <div
      class="btn-group btn-group-sm"
      role="group"
      id="riparias-obs-status-selector"
    >
      <ObservationStatusSelectorEntry
        entry-label="All"
        :checked="modelValue === null || modelValue === undefined"
        @entry-selected="myEmit(null)"
      ></ObservationStatusSelectorEntry>
      <ObservationStatusSelectorEntry
        entry-label="Seen"
        :checked="modelValue === 'seen'"
        :count="counts.seen"
        @entry-selected="myEmit('seen')"
      ></ObservationStatusSelectorEntry>
      <ObservationStatusSelectorEntry
        entry-label="Unseen"
        :checked="modelValue === 'unseen'"
        :count="counts.unseen"
        @entry-selected="myEmit('unseen')"
      ></ObservationStatusSelectorEntry>
    </div>

    <p class="m-0" v-if="counts.unseen > 0">
      <a @click="confirmationModalOpen = true" href="#"
        >Mark all observations as seen</a
      >
    </p>

    <confirmation-modal
      :modal-open="confirmationModalOpen"
      @click-yes="
        markAllObservationsAsSeen();
        confirmationModalOpen = false;
      "
      @click-no="confirmationModalOpen = false"
    ></confirmation-modal>
  </div>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import ObservationStatusSelectorEntry from "./ObservationStatusSelectorEntry.vue";
import ConfirmationModal from "./ConfirmationModal.vue";
import {DashboardFilters, EndpointsUrls} from "../interfaces";
import axios from "axios";
import {filtersToQuerystring} from "../helpers";

export default defineComponent({
  name: "ObservationStatusSelector",
  components: { ObservationStatusSelectorEntry, ConfirmationModal },
  props: {
    modelValue: {
      type: String,
    },
    filters: {
      type: Object as () => DashboardFilters,
      required: true,
    },
    endpointsUrls: {
      type: Object as () => EndpointsUrls,
      required: true,
    },
  },
  data: function () {
    return {
      confirmationModalOpen: false,
      counts: { seen: 0, unseen: 0 },
    };
  },
  emits: ["update:modelValue", "markAsSeenQueued"],
  methods: {
    myEmit: function (v: string | null) {
      this.$emit("update:modelValue", v);
    },
    markAllObservationsAsSeen: function () {
      axios
        .post(
          this.endpointsUrls.markObservationsAsSeenUrl,
          filtersToQuerystring(this.filters),
          { headers: { "X-CSRFToken": (window as any).CSRF_TOKEN } }
        )
        .then((response) => {
          if (response.data.queued === true) {
            this.$emit("markAsSeenQueued");
          }
        });
    },
    updateCounts: function (filters: DashboardFilters) {
      axios
        .get(this.endpointsUrls.observationsCounterUrl, {
          params: { ...filters, status: "seen" },
        })
        .then((response) => {
          this.counts.seen = response.data.count;
        });

      axios
        .get(this.endpointsUrls.observationsCounterUrl, {
          params: { ...filters, status: "unseen" },
        })
        .then((response) => {
          this.counts.unseen = response.data.count;
        });
    },
  },
  watch: {
    filters: {
      deep: true,
      immediate: true,
      handler: function (val) {
        this.updateCounts(val);
      },
    },
  },
});
</script>
