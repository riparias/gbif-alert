<template>
  <h3>{{ formattedCount }} {{ occurrenceStrPluralized }} matching selection</h3>
</template>

<script lang="ts">
import Vue from "vue";
import {DashboardFilters} from "../interfaces";
import axios from "axios";

export default Vue.extend({
  name: "OccurrencesCounter",
  props: {
    'filters': Object as () => DashboardFilters,
    'counterUrl': String
  },
  data: function () {
    return {
      'count': 0
    }
  },
  computed: {
    formattedCount: function(): string {
      return new Intl.NumberFormat().format(this.count)
    },
    occurrenceStrPluralized: function (): string {
      return this.count === 1 ? 'occurrence':'occurrences'
    }
  },
  methods: {
    updateCount: function (filters: DashboardFilters) {
      axios.get(this.counterUrl, {params: filters}).then(response => {
        this.count = response.data.count;
      })
    }
  },
  watch: {
    'filters': {
      deep: true,
      immediate: true,
      handler: function (val) {
        this.updateCount(val);
      }
    }
  },
})

</script>