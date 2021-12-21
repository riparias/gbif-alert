<template>
  <button type="button" class="btn btn-sm btn-dark">
    <span class="badge badge-light">{{ formattedCount }}</span> matching
    {{ observationStrPluralized }}
  </button>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { DashboardFilters } from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";

export default defineComponent({
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
      return new Intl.NumberFormat().format(this.count);
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
