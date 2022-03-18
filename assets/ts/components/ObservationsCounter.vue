<template>
  <span class="small"
    >{{ formattedCount }} matching {{ observationStrPluralized }}</span
  >
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { DashboardFilters } from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";
import { formatCount } from "../helpers";

export default defineComponent({
  // This component only shows a total counter, according to the passed filters (see also ObservationsCounterPerStatus)
  name: "ObservationsCounter",
  props: {
    filters: Object as () => DashboardFilters,
    counterUrl: {
      type: String,
      required: true,
    },
  },
  data: function () {
    return {
      count: 0,
    };
  },
  computed: {
    formattedCount: function (): string {
      return formatCount(this.count);
    },
    observationStrPluralized: function (): string {
      return this.count === 1 ? "observation" : "observations";
    },
  },
  methods: {
    updateCount: function (filters: DashboardFilters) {
      axios
        .get(this.counterUrl, {
          params: filters,
          paramsSerializer: filtersToQuerystring,
        })
        .then((response) => {
          this.count = response.data.count;
        });
    },
  },
  watch: {
    filters: {
      deep: true,
      immediate: true,
      handler: function (val) {
        this.updateCount(val);
      },
    },
  },
});
</script>
