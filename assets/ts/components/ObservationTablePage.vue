<template>
  <tbody>
    <tr v-for="occ in preparedObservations">
      <td>
        <span
          v-if="
            occ.hasOwnProperty('seenByCurrentUser') && // Anonymous users don't have the property, so if we don't do this all would appear us unseen
            occ.seenByCurrentUser === false
          "
          class="badge rounded-pill bg-danger gbif-alert-unseen-badge">{{ $t("message.unseen")}}</span
        >
      </td>
      <td>
        <a :href="occ.url">{{ occ.gbifId }}</a>
      </td>
      <td>{{ occ.lat }}, {{ occ.lon }}</td>
      <td>{{ occ.date }}</td>
      <td v-html="occ.displayNameHtml"></td>
      <td>{{ occ.datasetName }}</td>
    </tr>
  </tbody>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {JsonObservation} from "../interfaces";

interface ObservationForDisplay {
  // Similar to JsonObservation, but ready to display
  gbifId: number;
  lat: string;
  lon: string;
  date: string;
  datasetName: string;
  displayNameHtml: string;
  url: string;
  seenByCurrentUser?: boolean;
}

export default defineComponent({
  name: "ObservationTablePage",
  computed: {
    preparedObservations: function (): ObservationForDisplay[] {
      return this.observations.map((occ) => {
        return {
          gbifId: occ.gbifId,
          lat: occ.lat ? occ.lat.toFixed(3) : "",
          lon: occ.lon ? occ.lon.toFixed(3) : "",
          date: occ.date,
          displayNameHtml: occ.displayNameHtml,
          datasetName: this.truncateString(occ.datasetName, 30),
          url: this.observationPageUrlTemplate!.replace(
            "{stable_id}",
            occ.stableId
          ).replace("{origin}", window.location.pathname),
          seenByCurrentUser: occ.seenByCurrentUser,
        };
      });
    },
  },
  props: {
    observations: {
      // Only the subset for the page
      type: Array as () => JsonObservation[],
      default: function () {
        return [];
      },
    },
    observationPageUrlTemplate: {
      type: String,
      required: true,
    },
  },
  methods: {
    truncateString: function (str: string, num: number): string {
      if (str.length > num) {
        return str.slice(0, num) + "...";
      } else {
        return str;
      }
    },
  },
});
</script>
