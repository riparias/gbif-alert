<template>
  <div>
    <div class="row py-3">
      <div class="col col-sm-1">
        <label for="mapBaseSelector" class="col-form-label col-form-label-sm"
          >Base layer
        </label>
      </div>
      <div class="col">
        <select
          id="mapBaseSelector"
          v-model="mapBaseLayer"
          class="form-select form-select-sm"
        >
          <option v-for="l in availableMapBaseLayers" :value="l.id">
            {{ l.label }}
          </option>
        </select>
      </div>
      <div class="col col-sm-2">
        <label for="opacity" class="col-form-label col-form-label-sm"
          >Data layer opacity
        </label>
      </div>
      <div class="col">
        <input
          type="range"
          class="custom-range form-range"
          id="opacity"
          min="0"
          max="1"
          step="0.1"
          :value="dataLayerOpacity"
          @input="dataLayerOpacity = $event.target.valueAsNumber"
        />
      </div>
    </div>

    <Observations-Map
      :height="600"
      :initial-zoom="8"
      :initial-lat="50.501"
      :initial-lon="4.4764"
      :tile-server-aggregated-url-template="
        frontendConfig.apiEndpoints.tileServerAggregatedUrlTemplate
      "
      :tile-server-url-template="
        frontendConfig.apiEndpoints.tileServerUrlTemplate
      "
      :min-max-url="frontendConfig.apiEndpoints.minMaxOccPerHexagonUrl"
      :filters="filters"
      :show-counters="true"
      :base-layer-name="mapBaseLayer"
      :data-layer-opacity="dataLayerOpacity"
      :areas-to-show="filters.areaIds"
      :areas-endpoint-url-template="
        frontendConfig.apiEndpoints.areasUrlTemplate
      "
      :observation-page-url-template="
        frontendConfig.apiEndpoints.observationDetailsUrlTemplate
      "
    ></Observations-Map>
  </div>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {DashboardFilters, FrontEndConfig, SelectionEntry,} from "../interfaces";
import ObservationsMap from "./ObservationsMap.vue";

interface OuterObservationsMapComponentData {
  mapBaseLayer: string;
  availableMapBaseLayers: SelectionEntry[];
  dataLayerOpacity: number;
}

export default defineComponent({
  name: "OuterObservationsMap",
  components: {
    ObservationsMap,
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
  data: function (): OuterObservationsMapComponentData {
    return {
      availableMapBaseLayers: [
        { id: "toner", label: "Stamen Toner" },
        { id: "osmHot", label: "OSM HOT" },
        { id: "esriImagery", label: "ESRI World Imagery" },
      ],
      mapBaseLayer: "osmHot",
      dataLayerOpacity: 0.8,
    };
  },
});
</script>
