<template>
  Status:
  <div
    class="btn-group btn-group-sm"
    role="group"
    id="riparias-obs-status-selector"
  >
    <ObservationStatusSelectorEntry
      entry-label="All"
      :checked="modelValue === null"
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
</template>

<script lang="ts">
import { defineComponent } from "vue";
import ObservationStatusSelectorEntry from "./ObservationStatusSelectorEntry.vue";
import { DashboardFilters } from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";

export default defineComponent({
  name: "ObservationStatusSelector",
  components: { ObservationStatusSelectorEntry },
  props: {
    modelValue: {
      type: String,
    },
    filters: Object as () => DashboardFilters,
    counterUrl: {
      type: String,
      required: true,
    },
  },
  data: function () {
    return {
      counts: { seen: 0, unseen: 0 },
    };
  },
  emits: ["update:modelValue"],
  methods: {
    myEmit: function (v: string | null) {
      this.$emit("update:modelValue", v);
    },
    updateCounts: function (filters: DashboardFilters) {
      axios
        .get(this.counterUrl, {
          params: { ...filters, status: "seen" },
          paramsSerializer: filtersToQuerystring,
        })
        .then((response) => {
          this.counts.seen = response.data.count;
        });

      axios
        .get(this.counterUrl, {
          params: { ...filters, status: "unseen" },
          paramsSerializer: filtersToQuerystring,
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
