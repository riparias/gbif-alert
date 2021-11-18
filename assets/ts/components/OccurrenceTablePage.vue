<template>
  <tbody>
    <tr v-for="occ in preparedOccurrences">
      <th scope="row">
        <a :href="occ.url">{{ occ.gbifId }}</a>
      </th>
      <td>{{ occ.lat }}</td>
      <td>{{ occ.lon }}</td>
      <td>{{ occ.date }}</td>
      <td>{{ occ.speciesName }}</td>
      <td>{{ occ.datasetName }}</td>
    </tr>
  </tbody>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { JsonOccurrence } from "../interfaces";

interface OccurrencesForDisplay {
  // Similar to JsonOccurrence, but ready to display
  gbifId: number;
  lat: string;
  lon: string;
  date: string;
  speciesName: string;
  datasetName: string;
  url: string;
}

export default defineComponent({
  name: "OccurrenceTablePage",
  computed: {
    preparedOccurrences: function (): OccurrencesForDisplay[] {
      return this.occurrences.map((occ) => {
        return {
          gbifId: occ.gbifId,
          lat: occ.lat ? occ.lat.toFixed(4) : "",
          lon: occ.lon ? occ.lon.toFixed(4) : "",
          date: occ.date,
          speciesName: occ.speciesName,
          datasetName: occ.datasetName,
          url: this.occurrencePageUrlTemplate!.replace(
            "{stable_id}",
            occ.stableId
          ),
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
    occurrencePageUrlTemplate: String,
  },
});
</script>
