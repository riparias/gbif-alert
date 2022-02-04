<template>
  <button type="button" class="btn btn-sm btn-primary">
    Seen <span class="badge bg-secondary">{{ counts.seen }}</span> Unseen
    <span class="badge bg-secondary">{{ counts.unseen }}</span>
  </button>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { DashboardFilters } from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";

export default defineComponent({
  // This component shows seen and unseen counters,
  // It'll only work for authenticated users
  // (filters.status is discarded)
  // (see also the ObservationsCounterPerStatus component)
  name: "ObservationsCounterPerStatus",
  props: {
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
  methods: {
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
