<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import { Map, View } from "ol";
import OSM from "ol/source/OSM";
import Vue from "vue";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import { VectorTile as VectorTileLayer } from "ol/layer";
import { VectorTile as VectorTileSource } from "ol/source";

import "ol/ol.css";
import { MVT } from "ol/format";

declare interface MapContainerData {
  map: Map | null;
}

export default Vue.extend({
  name: "MapContainer",
  props: {
    height: Number, // Map height, in pixels
    initialZoom: Number,
    initialLat: Number,
    initialLon: Number,
    tileServerUrlTemplate: String,
  },
  data: function (): MapContainerData {
    return {
      map: null,
    };
  },
  computed: {
    basemapLayer: function (): TileLayer<any> {
      return new TileLayer({
        source: new OSM({
          url: "http://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        }),
      });
    },
    mapView: function (): View {
      return new View({
        zoom: this.initialZoom,
        center: fromLonLat([this.initialLon, this.initialLat]),
      });
    },
  },
  methods: {
    createDataLayer: function (): VectorTileLayer {
      return new VectorTileLayer({
        source: new VectorTileSource({
          format: new MVT(),
          url: this.tileServerUrlTemplate,
        }),
      });
    },
    createBasicMap: function (): Map {
      return new Map({
        target: this.$refs["map-root"] as HTMLInputElement,
        layers: [this.basemapLayer],
        view: this.mapView,
      });
    },
  },
  mounted() {
    this.map = this.createBasicMap();
  },
});
</script>
