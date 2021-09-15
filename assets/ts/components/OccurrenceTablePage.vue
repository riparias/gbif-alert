<template>
  <tbody>
    <tr v-for="occ in preparedOccurrences">
      <th scope="row">{{ occ.id }}</th>
      <td>{{ occ.lat }}</td>
      <td>{{ occ.lon }}</td>
      <td>{{ occ.date }}</td>
      <td>{{ occ.speciesName }}</td>
    </tr>
  </tbody>
</template>

<script lang="ts">
import Vue from "vue";
import { JsonOccurrence } from "../interfaces";

interface OccurrencesForDisplay {
  // Similar to JsonOccurrence, but ready to display
  id: string;
  lat: string;
  lon: string;
  date: string;
  speciesName: string;
}

export default Vue.extend({
  name: "OccurrenceTablePage",
  computed: {
    preparedOccurrences: function (): OccurrencesForDisplay[] {
      return this.occurrences.map((occ) => {
        return {
          id: occ.id,
          lat: occ.lat.toFixed(4),
          lon: occ.lon.toFixed(4),
          date: occ.date,
          speciesName: occ.speciesName,
        };
      });
    },
  },
  props: {
    occurrences: {
      // Only the subset for the page
      type: Array as () => JsonOccurrence[],
      default: function () {
        return [];
      },
    },
  },
});
</script>
