<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import Feature from "ol/Feature";
import Map from "ol/Map";
import { fromLonLat } from "ol/proj";

import "ol/ol.css";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import { baseLayers } from "../map_config";
import { ScaleLine } from "ol/control";
import { Circle } from "ol/geom";
import { Fill, Stroke, Style } from "ol/style";

declare interface SingleObservationMapData {
  map: Map | null;
}

export default defineComponent({
  name: "SingleObservationMap",
  props: {
    height: Number, // Map height, in pixels
    lon: {
      type: Number,
      required: true,
    },
    lat: {
      type: Number,
      required: true,
    },
    coordinatesUncertaintyInMeters: {
      type: Number,
      required: false,
    },
    defaultUncertaintyInMeters: {
      type: Number,
      default: 100, // If coordinatesUncertaintyInMeters is undefined, we'll use this radius
    },
    // Color to use when the uncertainty is correctly shown
    circleColorExactUncertainty: {
      type: String,
      default: "rgba(0,165,141,0.8)",
    },
    // Color to use when the default uncertainty is shown
    circleColorDefaultUncertainty: {
      type: String,
      default: "rgba(255,0,0,0.8)",
    },
    maxZoom: {
      type: Number,
      default: 19,
    },
  },
  data: function (): SingleObservationMapData {
    return {
      map: null,
    };
  },
  computed: {
    featureFillColor: function (): string {
      return this.coordinatesUncertaintyInMeters !== undefined
        ? this.circleColorExactUncertainty
        : this.circleColorDefaultUncertainty;
    },
    radiusToShow: function (): number {
      return this.coordinatesUncertaintyInMeters !== undefined
        ? this.coordinatesUncertaintyInMeters
        : this.defaultUncertaintyInMeters;
    },
  },
  methods: {
    createBasicMap: function () {
      const map = new Map({
        target: this.$refs["map-root"] as HTMLInputElement,
        layers: [baseLayers[1].layer],
      });

      const feature = new Feature({
        geometry: new Circle(
          fromLonLat([this.lon, this.lat]),
          this.radiusToShow
        ),
      });

      let pointLayer = new VectorLayer({
        source: new VectorSource({
          features: [feature],
        }),
        style: new Style({
          fill: new Fill({
            color: this.featureFillColor,
          }),
          stroke: new Stroke({ width: 1.25 }),
        }),
      });

      map.getView().fit(feature.getGeometry()!, { maxZoom: this.maxZoom + 1 }); // Avoid too much zoom
      map.getView().setZoom(map.getView().getZoom()! - 1); // Zoom up to have some padding

      map.addLayer(pointLayer);
      map.addControl(new ScaleLine());

      return map;
    },
  },
  mounted: function () {
    this.map = this.createBasicMap();
  },
});
</script>
