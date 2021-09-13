<template>
  <tbody>
    <tr v-for="occ in occurrences">
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

export default Vue.extend({
  name: "OccurrenceTablePage",
  props: {
    occurrences: {
      // Only the subset for the page
      type: Array,
      default: function () {
        return [];
      },
    },
  },
});
</script>
