<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import { Feature, Map, View } from "ol";
import { defineComponent } from "vue";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import { Vector, VectorTile as VectorTileLayer } from "ol/layer";
import { OSM, Stamen, VectorTile as VectorTileSource } from "ol/source";
import { scaleSequentialLog, ScaleSequential } from "d3-scale";
import { interpolateReds } from "d3-scale-chromatic";
import { hsl } from "d3-color";
import { DashboardFilters } from "../interfaces";
import "ol/ol.css";
import { GeoJSON, MVT } from "ol/format";
import { Fill, Stroke, Style, Text } from "ol/style";
import axios from "axios";
import RenderFeature from "ol/render/Feature";
import VectorSource from "ol/source/Vector";

interface BaseLayerEntry {
  name: string;
  layer: TileLayer<any>;
}

declare interface MapContainerData {
  map: Map | null;
  dataLayer: VectorTileLayer | null;
  HexMinOccCount: Number;
  HexMaxOccCount: Number;
  availableBaseLayers: BaseLayerEntry[];
  ripariasAreaLayer: Vector<any>;
}

interface OlStyleFunction {
  (feature: Feature<any> | RenderFeature): Style;
}

export default defineComponent({
  name: "MapContainer",
  props: {
    height: Number, // Map height, in pixels
    initialZoom: Number,
    initialLat: Number,
    initialLon: Number,
    tileServerUrlTemplate: String,
    filters: Object as () => DashboardFilters,
    minMaxUrl: String,
    showCounters: Boolean,
    baseLayerName: String,

    ripariasGeojsonUrl: String,
    showRipariasArea: Boolean,

    dataLayerOpacity: Number,
  },
  data: function (): MapContainerData {
    return {
      map: null,
      dataLayer: null,
      HexMinOccCount: 1,
      HexMaxOccCount: 1,
      availableBaseLayers: [
        {
          name: "toner",
          layer: new TileLayer({ source: new Stamen({ layer: "toner" }) }),
        },
        {
          name: "osmHot",
          layer: new TileLayer({
            source: new OSM({
              url: "http://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
            }),
          }),
        },
      ],
      ripariasAreaLayer: new Vector({
        source: new VectorSource({
          format: new GeoJSON(),
          url: this.ripariasGeojsonUrl,
        }),
        style: new Style({
          stroke: new Stroke({
            color: "#0b6efd",
            width: 3,
          }),
        }),
        zIndex: 1000,
      }),
    };
  },
  watch: {
    dataLayerOpacity: {
      handler: function (val) {
        if (this.dataLayer) {
          this.dataLayer.setOpacity(val);
        }
      },
    },
    showRipariasArea: function () {
      this.updateRipariasArea();
    },
    baseLayerName: {
      handler: function (newVal: string) {
        if (this.map) {
          let layers = this.map.getLayers();
          layers.removeAt(0);
          layers.insertAt(0, this.selectedBaseLayer);
        }
      },
    },
    filters: {
      handler: function () {
        this.replaceDataLayer();
      },
      deep: true,
    },
    HexMinOccCount: {
      handler: function () {
        if (this.dataLayer) {
          this.dataLayer.setStyle(this.dataLayerStyleFunction);
        }
      },
    },
    HexMaxOccCount: {
      handler: function () {
        if (this.dataLayer) {
          this.dataLayer.setStyle(this.dataLayerStyleFunction);
        }
      },
    },
  },
  computed: {
    selectedBaseLayer: function (): TileLayer<any> {
      return this.selectedBaseLayerEntry.layer;
    },
    selectedBaseLayerEntry: function (): BaseLayerEntry {
      const found = this.availableBaseLayers.find(
        (l) => this.baseLayerName === l.name
      );
      if (found) {
        return found;
      } else {
        return this.availableBaseLayers[0]; // First one as default
      }
    },
    colorScale: function (): ScaleSequential<string> {
      return scaleSequentialLog(interpolateReds).domain([
        this.HexMinOccCount,
        this.HexMaxOccCount,
      ]);
    },
    dataLayerStyleFunction: function (): OlStyleFunction {
      let vm = this;
      return function (feature: Feature<any> | RenderFeature): Style {
        const featuresCount = feature.getProperties()["count"];
        const fillColor = vm.colorScale(featuresCount);
        const textValue = vm.showCounters ? "" + featuresCount : "";

        return new Style({
          stroke: new Stroke({
            color: "grey",
            width: 1,
          }),
          fill: new Fill({
            color: fillColor,
          }),
          text: new Text({
            text: textValue,
            fill: new Fill({ color: vm.legibleColor(fillColor) }),
          }),
        });
      };
    },
    mapView: function (): View {
      return new View({
        zoom: this.initialZoom,
        center: fromLonLat([this.initialLon, this.initialLat]),
      });
    },
    filtersAsQueryString: function (): string {
      const filtersStringinfied = Object.fromEntries(
        Object.entries(this.filters).map(([k, v]) => [k, String(v)])
      );
      return new URLSearchParams(filtersStringinfied).toString();
    },
  },
  methods: {
    updateRipariasArea: function () {
      if (this.map) {
        if (this.showRipariasArea) {
          this.map.addLayer(this.ripariasAreaLayer);
        } else {
          this.map.removeLayer(this.ripariasAreaLayer);
        }
      }
    },
    loadOccMinMax: function (zoomLevel: number, filters: DashboardFilters) {
      let params = { ...filters } as any;
      params.zoom = zoomLevel;

      axios.get(this.minMaxUrl, { params: params }).then((response) => {
        this.HexMinOccCount = response.data.min;
        this.HexMaxOccCount = response.data.max;
      });
    },
    replaceDataLayer: function (): void {
      if (this.map) {
        if (this.dataLayer) {
          this.map.removeLayer(this.dataLayer);
        }
        this.dataLayer = this.createDataLayer();
        this.map.addLayer(this.dataLayer);
      }
    },
    legibleColor: function (color: string): string {
      return hsl(color).l > 0.5 ? "#000" : "#fff";
    },
    createDataLayer: function (): VectorTileLayer {
      return new VectorTileLayer({
        source: new VectorTileSource({
          format: new MVT(),
          url: this.tileServerUrlTemplate + "?" + this.filtersAsQueryString,
        }),
        style: this.dataLayerStyleFunction,
        opacity: this.dataLayerOpacity,
      });
    },
    createBasicMap: function (): Map {
      const map = new Map({
        target: this.$refs["map-root"] as HTMLInputElement,
        layers: [this.selectedBaseLayer],
        view: this.mapView,
      });

      return map;
    },
  },
  mounted() {
    this.loadOccMinMax(this.initialZoom, this.filters);
    this.map = this.createBasicMap();
    this.replaceDataLayer();
    this.updateRipariasArea();
  },
});
</script>
