<template>
  <div ref="map-root"
       :style="{width: '100%', height: height + 'px'}">
  </div>
</template>

<script lang="ts">
  import View from 'ol/View'
  import Map from 'ol/Map'
  import TileLayer from 'ol/layer/Tile'
  import OSM from 'ol/source/OSM'

  import 'ol/ol.css'
  import Vue from "vue";
  import {fromLonLat} from "ol/proj";

  export default Vue.extend( {
    name: 'MapContainer',
    components: {},
    props: {
      height: Number, // Map height, in pixels
      initialZoom: Number,
      initialLat: Number,
      initialLon: Number
    },
    mounted() {
      new Map({
        target: this.$refs['map-root'] as HTMLInputElement,
        layers: [
          new TileLayer({
            source: new OSM({url: "http://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"})
          }),
        ],
        view: new View({
          zoom: this.initialZoom,
          center: fromLonLat([this.initialLon, this.initialLat]),
        }),
      })
    },
  });
</script>