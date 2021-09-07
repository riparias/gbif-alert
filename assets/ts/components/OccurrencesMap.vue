<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import {Feature, Map, View} from "ol";
import OSM from "ol/source/OSM";
import Vue from "vue";
import {fromLonLat} from "ol/proj";
import TileLayer from "ol/layer/Tile";
import {VectorTile as VectorTileLayer} from "ol/layer";
import {Stamen, VectorTile as VectorTileSource} from "ol/source";
import * as d3 from "d3";
import {DashboardFilters} from "../interfaces";
import "ol/ol.css";
import {MVT} from "ol/format";
import {Fill, Stroke, Style, Text} from "ol/style";
import axios from "axios";
import RenderFeature from "ol/render/Feature";

declare interface MapContainerData {
  map: Map | null;
  dataLayer: VectorTileLayer | null;
  HexMinOccCount: Number,
  HexMaxOccCount: Number
}

interface OlStyleFunction {
  (feature: Feature<any> | RenderFeature): Style;
}

export default Vue.extend({
  name: "MapContainer",
  props: {
    height: Number, // Map height, in pixels
    initialZoom: Number,
    initialLat: Number,
    initialLon: Number,
    tileServerUrlTemplate: String,
    filters: Object as () => DashboardFilters,
    minMaxUrl: String,
    showCounters: Boolean
  },
  data: function (): MapContainerData {
    return {
      map: null,
      dataLayer: null,
      HexMinOccCount: 1,
      HexMaxOccCount: 1
    };
  },
  watch: {
    HexMinOccCount: {
      handler: function () {
        this.replaceDataLayer(); // TODO: restyle without full replace?
      },
    },
    HexMaxOccCount: {
      handler: function () {
        this.replaceDataLayer(); // TODO: restyle without full replace?
      },
    },
  },
  computed: {
    colorScale: function (): d3.ScaleSequential<string> {
      return d3.scaleSequentialLog(d3.interpolateReds)
          .domain([this.HexMinOccCount, this.HexMaxOccCount])
    },
    dataLayerStyleFunction: function (): OlStyleFunction {
      let vm = this;
      return function (feature: Feature<any> | RenderFeature): Style {
        const featuresCount = feature.getProperties()['count']
        const fillColor = vm.colorScale(featuresCount);
        const textValue = vm.showCounters ? '' + featuresCount : ''

        return new Style({
          stroke: new Stroke({
            color: 'grey',
            width: 1,
          }),
          fill: new Fill({
            color: fillColor
          }),
          text: new Text({
            text: textValue,
            fill: new Fill({color: vm.legibleColor(fillColor)})
          })
        })
      }
    },
    basemapLayer: function (): TileLayer<any> {
      return new TileLayer({
        source: new Stamen({
          layer: "toner",
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
    loadOccMinMax: function (zoomLevel: number, filters: DashboardFilters) {
      let params = {...filters} as any;
      params.zoom = zoomLevel;

      axios.get(this.minMaxUrl, {params: params}).then(response => {
        this.HexMinOccCount = response.data.min;
        this.HexMaxOccCount = response.data.max;
      })
    },
    replaceDataLayer: function (): void {
      if (this.map) {
        if (this.dataLayer) {
          this.map.removeLayer(this.dataLayer)
        }
        this.dataLayer = this.createDataLayer();
        this.map.addLayer(this.dataLayer);
      }
    },
    legibleColor: function (color: string): string {
      return d3.hsl(color).l > 0.5 ? "#000" : "#fff"
    },
    createDataLayer: function (): VectorTileLayer {
      return new VectorTileLayer({
        source: new VectorTileSource({
          format: new MVT(),
          url: this.tileServerUrlTemplate,
        }),
        style: this.dataLayerStyleFunction,
        opacity: 0.8
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
    this.loadOccMinMax(this.initialZoom, this.filters);
    this.map = this.createBasicMap();
    this.replaceDataLayer();
  },
});
</script>
