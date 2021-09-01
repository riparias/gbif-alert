<template>
  <div ref="map-root"
       style="width: 600px; height: 500px; position:absolute;">
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
    props: {},
    mounted() {
      new Map({
        target: this.$refs['map-root'] as HTMLInputElement,
        layers: [

          new TileLayer({
            source: new OSM()
          }),
        ],
        view: new View({
          zoom: 7,
          center: fromLonLat([4.47, 50.50]),
        }),
      })
    },
  });
</script>