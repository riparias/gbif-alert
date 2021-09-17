<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import Vue from "vue";
import { Feature, Map, View } from "ol";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import { OSM } from "ol/source";

import "ol/ol.css";
import { Vector } from "ol/layer";
import { Vector as VectorSource } from "ol/source";
import { Point } from "ol/geom";
import { Fill, Stroke, Style } from "ol/style";
import CircleStyle from "ol/style/Circle";

export default Vue.extend({
  name: "SingleOccurrenceMap",
  props: {
    height: Number, // Map height, in pixels
    lon: Number,
    lat: Number,
  },
  data: function () {
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

      let pointLayer = new Vector({
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
