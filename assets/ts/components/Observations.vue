<template>
  <div>
    <div class="row">
      <div class="col">
        <Observations-counter
          class="float-end"
          :counter-url="frontendConfig.apiEndpoints.observationsCounterUrl"
          :filters="filters"
        ></Observations-counter>
      </div>
    </div>
    <div class="row">
      <div class="col">
        <Observations-time-line
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
          v-model="selectedTabId"
          :tabs="availableTabs"
        ></Tab-switcher>
      </div>
    </div>

    <div class="row">
      <div class="col">
        <div class="px-4 bg-light border-start border-end">
          <OuterObservationsMap
            v-show="selectedTabId === 'mapView'"
            :filters="filters"
            :frontend-config="frontendConfig"
          ></OuterObservationsMap>

          <Observations-Table
            v-show="selectedTabId === 'tableView'"
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
import {defineComponent} from "vue";

import ObservationsTimeLine from "./ObservationTimeLine.vue";
import TabSwitcher from "./TabSwitcher.vue";
import ObservationsCounter from "./ObservationsCounter.vue";
import ObservationsTable from "./ObservationsTable.vue";
import OuterObservationsMap from "./OuterObservationsMap.vue";
import {DashboardFilters, DateRange, FrontEndConfig} from "../interfaces";

interface Tab {
  name: string;
  id: string;
}

interface ObservationsComponentData {
  selectedTabId: string;
  availableTabs: Tab[];
}

export default defineComponent({
  name: "Observations",
  components: {
    ObservationsTimeLine,
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
      selectedTabId: "mapView",
      availableTabs: [
          {name: this.$t("message.mapView"), id: "mapView"},
          {name: this.$t("message.tableView"), id: "tableView"}
      ],
    };
  },
});
</script>
