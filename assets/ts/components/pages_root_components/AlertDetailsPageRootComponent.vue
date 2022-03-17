<template>
  <bootstrap-alert
    v-if="showInProgressMessage"
    @clickClose="showInProgressMessage = false"
    alert-type="success"
    class="my-2"
  >
    <i class="bi bi-info-circle"></i>
    The observations are marked as seen in the background. This might takes a
    couple of minutes if there are a lot of observations. Don't hesitate to
    refresh the page.
  </bootstrap-alert>

  <div class="my-3">
    <ObservationStatusSelector
      v-model="filters.status"
      :endpoints-urls="frontendConfig.apiEndpoints"
      :filters="filters"
      @markAsSeenQueued="showInProgressMessage = true"
    ></ObservationStatusSelector>
  </div>

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
import { dateTimeToFilterParam } from "../../helpers";
import ObservationStatusSelector from "../ObservationStatusSelector.vue";
import BootstrapAlert from "../BootstrapAlert.vue";

declare const ripariasConfig: FrontEndConfig;
declare const alertId: number;

interface AlertDetailsPageRootComponentData {
  alertId: number;
  frontendConfig: FrontEndConfig;
  filters: DashboardFilters;
  debouncedUpdateDateFilters: null | DebouncedFunc<(range: DateRange) => void>;
  showInProgressMessage: boolean;
}

export default defineComponent({
  name: "AlertDetailsPageRootComponent",
  components: {
    Observations,
    ObservationStatusSelector,
    BootstrapAlert,
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
      showInProgressMessage: false,
    };
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
