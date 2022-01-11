<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script lang="ts">
import { Collection, Feature, Map, View } from "ol";
import { defineComponent, PropType } from "vue";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import { VectorTile as VectorTileLayer } from "ol/layer";
import OSM from "ol/source/OSM";
import Stamen from "ol/source/Stamen";
import VectorTileSource from "ol/source/VectorTile";
import { scaleSequentialLog, ScaleSequential } from "d3-scale";
import { interpolateReds } from "d3-scale-chromatic";
import { hsl } from "d3-color";
import { BaseLayerEntry, DashboardFilters } from "../interfaces";
import "ol/ol.css";
import { GeoJSON, MVT } from "ol/format";
import { Fill, Stroke, Style, Text } from "ol/style";
import axios from "axios";
import RenderFeature from "ol/render/Feature";
import VectorSource from "ol/source/Vector";
import { filtersToQuerystring } from "../helpers";
import LayerGroup from "ol/layer/Group";
import VectorLayer from "ol/layer/Vector";
import { Geometry } from "ol/geom";
import BaseLayer from "ol/layer/Base";
import { baseLayers } from "../map_config";

interface MapContainerData {
  map: Map | null;
  dataLayer: VectorTileLayer | null;
  HexMinOccCount: Number;
  HexMaxOccCount: Number;
  availableBaseLayers: BaseLayerEntry[];
  areasOverlayCollection: Collection<VectorLayer<VectorSource<Geometry>>>;
}

interface OlStyleFunction {
  (feature: Feature<any> | RenderFeature): Style;
}

export default defineComponent({
  name: "MapContainer",
  props: {
    height: {
      type: Number, // Map height, in pixels
      required: true,
    },
    initialZoom: {
      type: Number,
      required: true,
    },
    initialLat: {
      type: Number,
      required: true,
    },
    initialLon: {
      type: Number,
      required: true,
    },
    tileServerUrlTemplate: String,
    filters: {
      type: Object as () => DashboardFilters,
      required: true,
    },
    minMaxUrl: {
      type: String,
      required: true,
    },
    showCounters: Boolean,
    baseLayerName: String,

    dataLayerOpacity: Number,

    areasToShow: {
      type: Array as PropType<Array<number>>, // Array of area ids
      default: [],
    },

    areasEndpointUrlTemplate: {
      type: String,
      required: true,
    },
  },
  data: function () {
    return {
      map: null,
      dataLayer: null,
      HexMinOccCount: 1,
      HexMaxOccCount: 1,
      availableBaseLayers: baseLayers,
      areasOverlayCollection: new Collection(),
    } as MapContainerData;
  },
  watch: {
    areasToShow: {
      handler: function (val) {
        this.refreshAreas(val);
      },
    },
    dataLayerOpacity: {
      handler: function (val) {
        if (this.dataLayer) {
          this.dataLayer.setOpacity(val);
        }
      },
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
    selectedBaseLayer: function (): TileLayer<Stamen> | TileLayer<OSM> {
      return this.selectedBaseLayerEntry.layer;
    },
    selectedBaseLayerEntry: function (): BaseLayerEntry {
      const availableBaseLayers = this.availableBaseLayers as BaseLayerEntry[]; // Don't understand why the type is not inferred automatically

      const found = availableBaseLayers.find(
        (l) => this.baseLayerName === l.name
      );
      if (found) {
        return found;
      } else {
        return availableBaseLayers[0]; // First one as default
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
  },
  methods: {
    refreshAreas: function (areaIds: number[]): void {
      this.areasOverlayCollection.clear();

      for (const areaId of areaIds) {
        axios
          .get(this.areasEndpointUrlTemplate.replace("{id}", areaId.toString()))
          .then((response) => {
            const vectorSource = new VectorSource({
              features: new GeoJSON().readFeatures(response.data, {
                dataProjection: "EPSG:4326",
                featureProjection: "EPSG:3857",
              }),
            });

            const vectorLayer = new VectorLayer({
              source: vectorSource,
              style: new Style({
                stroke: new Stroke({
                  color: "#0b6efd",
                  width: 3,
                }),
              }),
            });

            this.areasOverlayCollection.push(vectorLayer);
          });
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
          this.map.removeLayer(this.dataLayer as VectorTileLayer);
        }
        this.dataLayer = this.createDataLayer();
        this.map.addLayer(this.dataLayer as VectorTileLayer);
      }
    },
    legibleColor: function (color: string): string {
      return hsl(color).l > 0.5 ? "#000" : "#fff";
    },
    createDataLayer: function (): VectorTileLayer {
      return new VectorTileLayer({
        source: new VectorTileSource({
          format: new MVT(),
          url:
            this.tileServerUrlTemplate +
            "?" +
            filtersToQuerystring(this.filters),
        }),
        style: this.dataLayerStyleFunction,
        opacity: this.dataLayerOpacity,
      });
    },
    createBasicMap: function (): Map {
      return new Map({
        target: this.$refs["map-root"] as HTMLInputElement,
        layers: [
          this.selectedBaseLayer,
          new LayerGroup({
            layers: this
              .areasOverlayCollection as unknown as Collection<BaseLayer>,
            zIndex: 1000,
          }),
        ],
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
