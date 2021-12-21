<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import Feature from "ol/Feature";
import Map from "ol/Map";
import View from "ol/View";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import OSM from "ol/source/OSM";

import "ol/ol.css";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import Point from "ol/geom/Point";
import Fill from "ol/style/Fill";
import Stroke from "ol/style/Stroke";
import Style from "ol/style/Style";
import CircleStyle from "ol/style/Circle";

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
  },
  data: function (): SingleObservationMapData {
    return {
      map: null,
    };
  },
  methods: {
    createBasicMap: function () {
      const map = new Map({
        target: this.$refs["map-root"] as HTMLInputElement,
        layers: [
          new TileLayer({
            source: new OSM({
              url: "http://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
            }),
          }),
        ],
        view: new View({
          zoom: 10,
          center: fromLonLat([this.lon, this.lat]),
        }),
      });

      let pointLayer = new VectorLayer({
        source: new VectorSource({
          features: [
            new Feature({
              geometry: new Point(fromLonLat([this.lon, this.lat])),
            }),
          ],
        }),
        style: new Style({
          image: new CircleStyle({
            radius: 5,
            fill: new Fill({ color: "#ff7f7f" }),
            stroke: new Stroke({ color: "red", width: 2 }),
          }),
        }),
      });

      map.addLayer(pointLayer);

      return map;
    },
  },
  mounted: function () {
    this.map = this.createBasicMap();
  },
});
</script>
