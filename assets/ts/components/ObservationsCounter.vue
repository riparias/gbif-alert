<template>
  <span class="small">
      {{ $tc('message.matchingObservations', count, {count: count}) }}
  </span>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {DashboardFilters} from "../interfaces";
import axios from "axios";

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
  methods: {
    updateCount: function (filters: DashboardFilters) {
      axios
        .get(this.counterUrl, {
          params: filters,

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
