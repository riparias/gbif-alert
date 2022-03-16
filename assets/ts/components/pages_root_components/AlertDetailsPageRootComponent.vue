<template>
  <ObservationStatusSelector
    v-model="filters.status"
    :counter-url="frontendConfig.apiEndpoints.observationsCounterUrl"
    :filters="filters"
  ></ObservationStatusSelector>

  <p>
    <a @click="markAllObservationsAsSeen()" href="#"
      >Mark all observations as seen</a
    >
  </p>

  <Observations
    :frontend-config="frontendConfig"
    :filters="filters"
    @selectedDateRangeUpdated="debouncedUpdateDateFilters"
  ></Observations>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import Observations from "../Observations.vue";
import { DashboardFilters, DateRange, FrontEndConfig } from "../../interfaces";
import axios from "axios";
import { debounce, DebouncedFunc } from "lodash";
import { dateTimeToFilterParam, filtersToQuerystring } from "../../helpers";
import ObservationStatusSelector from "../ObservationStatusSelector.vue";

declare const ripariasConfig: FrontEndConfig;
declare const alertId: number;

interface AlertDetailsPageRootComponentData {
  alertId: number;
  frontendConfig: FrontEndConfig;
  filters: DashboardFilters;
  debouncedUpdateDateFilters: null | DebouncedFunc<(range: DateRange) => void>;
}

export default defineComponent({
  name: "AlertDetailsPageRootComponent",
  components: {
    Observations,
    ObservationStatusSelector,
  },
  data: function (): AlertDetailsPageRootComponentData {
    return {
      frontendConfig: ripariasConfig,
      alertId: alertId,
      filters: {
        speciesIds: [],
        datasetsIds: [],
        areaIds: [],
        initialDataImportIds: [],
        startDate: null,
        endDate: null,
        status: null,
      },
      debouncedUpdateDateFilters: null,
    };
  },
  methods: {
    markAllObservationsAsSeen: function () {
      axios
        .post(
          this.frontendConfig.apiEndpoints.markObservationsAsSeenUrl,
          filtersToQuerystring(this.filters),
          { headers: { "X-CSRFToken": (window as any).CSRF_TOKEN } }
        )
        .then((response) => {
          console.log("response");
        });
    },
  },
  mounted: function () {
    axios
      .get(this.frontendConfig.apiEndpoints.alertAsFiltersUrl, {
        params: { alert_id: this.alertId },
      })
      .then((response) => {
        this.filters = response.data;
      });
  },
  created() {
    // Approach stolen  from: https://dmitripavlutin.com/vue-debounce-throttle/
    this.debouncedUpdateDateFilters = debounce((range) => {
      this.filters.startDate = dateTimeToFilterParam(range.start);
      this.filters.endDate = dateTimeToFilterParam(range.end);
    }, 300);
  },
  beforeUnmount() {
    if (this.debouncedUpdateDateFilters) {
      this.debouncedUpdateDateFilters.cancel();
    }
  },
});
</script>
