<template>
  <div>
    <div class="row">
      <div class="col">
        <Custom-observations-time-line
          :filters="filters"
          :histogram-data-url="
            frontendConfig.apiEndpoints.observationsHistogramDataUrl
          "
          @selectedDateRangeUpdated="rangeUpdated"
        />
      </div>
    </div>

    <div class="row mt-3">
      <div class="col">
        <Tab-switcher
          v-model="selectedTab"
          :tab-names="availableTabs"
        ></Tab-switcher>
      </div>
      <div class="col align-self-center">
        <Observations-counter
          class="float-end"
          :counter-url="frontendConfig.apiEndpoints.observationsCounterUrl"
          :filters="filters"
        ></Observations-counter>
      </div>
    </div>

    <div class="row">
      <div class="col">
        <div class="px-4 bg-light border-start border-end">
          <OuterObservationsMap
            v-show="selectedTab === 'Map view'"
            :filters="filters"
            :frontend-config="frontendConfig"
          ></OuterObservationsMap>

          <Observations-Table
            v-show="selectedTab === 'Table view'"
            :filters="filters"
            :observations-json-url="
              frontendConfig.apiEndpoints.observationsJsonUrl
            "
            :observation-page-url-template="
              frontendConfig.apiEndpoints.observationDetailsUrlTemplate
            "
          >
          </Observations-Table>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";

import CustomObservationsTimeLine from "./CustomObservationTimeLine.vue";
import TabSwitcher from "./TabSwitcher.vue";
import ObservationsCounter from "./ObservationsCounter.vue";
import ObservationsTable from "./ObservationsTable.vue";
import OuterObservationsMap from "./OuterObservationsMap.vue";
import { DashboardFilters, DateRange, FrontEndConfig } from "../interfaces";

interface ObservationsComponentData {
  selectedTab: string;
  availableTabs: string[];
}

export default defineComponent({
  name: "Observations",
  components: {
    CustomObservationsTimeLine,
    TabSwitcher,
    ObservationsCounter,
    ObservationsTable,
    OuterObservationsMap,
  },
  props: {
    frontendConfig: {
      required: true,
      type: Object as () => FrontEndConfig,
    },
    filters: {
      required: true,
      type: Object as () => DashboardFilters,
    },
  },
  emits: ["selectedDateRangeUpdated"],
  methods: {
    rangeUpdated: function (newRange: DateRange) {
      // Re-emit the same thing to parent, is there a better way?
      this.$emit("selectedDateRangeUpdated", newRange);
    },
  },
  data: function (): ObservationsComponentData {
    return {
      selectedTab: "Map view",
      availableTabs: ["Map view", "Table view"],
    };
  },
});
</script>
