<template>
  <div ref="map-root" :style="{ width: '100%', height: height + 'px' }"></div>
  <div ref="popup-root" title="Observations at this location"></div>
</template>

<script lang="ts">
import {Collection, Feature, Map, Overlay, View} from "ol";
import {defineComponent, PropType} from "vue";
import {fromLonLat} from "ol/proj";
import TileLayer from "ol/layer/Tile";
import {VectorTile as VectorTileLayer} from "ol/layer";
import OSM from "ol/source/OSM";
import StadiaMaps from 'ol/source/StadiaMaps.js';
import VectorTileSource from "ol/source/VectorTile";
import {ScaleSequential, scaleSequentialLog} from "d3-scale";
import {interpolateReds} from "d3-scale-chromatic";
import {BaseLayerEntry, DashboardFilters, EndpointsUrls, MapConfig} from "../interfaces";
import "ol/ol.css";
import {GeoJSON, MVT} from "ol/format";
import {Circle, Fill, Stroke, Style, Text} from "ol/style";
import axios from "axios";
import RenderFeature from "ol/render/Feature";
import VectorSource from "ol/source/Vector";
import {filtersToQuerystring, legibleColor} from "../helpers";
import LayerGroup from "ol/layer/Group";
import VectorLayer from "ol/layer/Vector";
import BaseLayer from "ol/layer/Base";
import {baseLayers} from "../map_config";
import {Popover} from "bootstrap";
import {StyleFunction} from "ol/style/Style";

interface ObservationMapData {
  map: Map | null;
  aggregatedDataLayer: VectorTileLayer<Feature> | null;
  simpleDataLayer: VectorTileLayer<Feature> | null;
  popup: Overlay;
  HexMinOccCount: Number;
  HexMaxOccCount: Number;
  availableBaseLayers: BaseLayerEntry[];
  areasOverlayCollection: Collection<VectorLayer<Feature>>;
  popover: Popover | null;
}

export default defineComponent({
  name: "ObservationsMap",
  props: {
    height: {
      type: Number, // Map height, in pixels
      required: true,
    },
    initialPosition: {
      type: Object as () => MapConfig,
      required: true,
    },
    apiEndpoints: {
      type: Object as () => EndpointsUrls,
      required: true,
    },
    filters: {
      type: Object as () => DashboardFilters,
      required: true,
    },
    baseLayerName: String,
    dataLayerOpacity: Number,
    areasToShow: {
      type: Array as PropType<Array<Number>>, // Array of area ids
      default: [],
    },
    layerSwitchZoomLevel: {
      // At which zoom level do we switch from the aggregated hexagons to the "individual observation" layer
      type: Number,
      default: 13,
    },
    zoomLevelMinMaxQuery: {
      type: Number,
      required: true,
    },
  },
  data: function () {
    return {
      map: null,
      aggregatedDataLayer: null,
      simpleDataLayer: null,
      popup: new Overlay({}),
      HexMinOccCount: 1,
      HexMaxOccCount: 1,
      availableBaseLayers: baseLayers,
      areasOverlayCollection: new Collection(),
      popover: null,
    } as ObservationMapData;
  },
  watch: {
    areasToShow: {
      handler: function (val) {
        this.refreshAreas(val);
      },
    },
    dataLayerOpacity: {
      handler: function (val) {
        if (this.aggregatedDataLayer) {
          this.aggregatedDataLayer.setOpacity(val);
        }
        if (this.simpleDataLayer) {
          this.simpleDataLayer.setOpacity(val);
        }
      },
    },
    baseLayerName: {
      handler: function () {
        if (this.map) {
          let layers = this.map.getLayers();
          layers.removeAt(0);
          layers.insertAt(0, this.selectedBaseLayer);
        }
      },
    },
    filters: {
      handler: function () {
        this.replaceDataLayers();
      },
      deep: true,
    },
    HexMinOccCount: {
      handler: function () {
        if (this.aggregatedDataLayer) {
          this.aggregatedDataLayer.setStyle(
              this.aggregatedDataLayerStyleFunction
          );
        }
      },
    },
    HexMaxOccCount: {
      handler: function () {
        if (this.aggregatedDataLayer) {
          this.aggregatedDataLayer.setStyle(
              this.aggregatedDataLayerStyleFunction
          );
        }
      },
    },
  },
  computed: {
    selectedBaseLayer: function (): TileLayer<StadiaMaps> | TileLayer<OSM> {
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
    aggregatedDataLayerStyleFunction: function (): StyleFunction {
      let vm = this;
      return function (feature: Feature<any> | RenderFeature): Style {
        const featuresCount = feature.getProperties()["count"];
        const fillColor = vm.colorScale(featuresCount);
        const textColor = legibleColor(fillColor);

        return new Style({
          stroke: new Stroke({
            color: "grey",
            width: 1,
          }),
          fill: new Fill({
            color: fillColor,
          }),
          text: new Text({
            text: featuresCount.toString(),
            fill: new Fill({color: textColor}),
          }),
        });
      };
    },
    mapView: function (): View {
      return new View({
        zoom: this.initialPosition.initialZoom,
        center: fromLonLat([this.initialPosition.initialLon, this.initialPosition.initialLat]),
      });
    },
  },
  methods: {
    refreshAreas: function (areaIds: number[]): void {
      this.areasOverlayCollection.clear();

      for (const areaId of areaIds) {
        axios
            .get(this.apiEndpoints.areasUrlTemplate.replace("{id}", areaId.toString()))
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
      let params = {...filters} as any;
      params.zoom = zoomLevel;

      axios.get(this.apiEndpoints.minMaxOccPerHexagonUrl, {params: params}).then((response) => {
        this.HexMinOccCount = response.data.min;
        this.HexMaxOccCount = response.data.max;
      });
    },
    replaceDataLayers: function (): void {
      this.replaceAggregatedDataLayer();
      this.replaceSimpleDataLayer();
    },
    replaceSimpleDataLayer: function (): void {
      if (this.map) {
        if (this.simpleDataLayer) {
          this.map.removeLayer(this.simpleDataLayer as VectorTileLayer<Feature>);
        }
        this.simpleDataLayer = this.createSimpleDataLayer();
        this.map.addLayer(this.simpleDataLayer as VectorTileLayer<Feature>);
      }
    },
    replaceAggregatedDataLayer: function (): void {
      if (this.map) {
        if (this.aggregatedDataLayer) {
          this.map.removeLayer(this.aggregatedDataLayer as VectorTileLayer<Feature>);
        }
        this.loadOccMinMax(this.zoomLevelMinMaxQuery, this.filters);
        this.aggregatedDataLayer = this.createAggregatedDataLayer();
        this.map.addLayer(this.aggregatedDataLayer as VectorTileLayer<Feature>);
      }
    },
    createSimpleDataLayer: function (): VectorTileLayer<Feature> {
      return new VectorTileLayer({
        source: new VectorTileSource({
          format: new MVT(),
          url:
              this.apiEndpoints.tileServerUrlTemplate +
              "?" +
              filtersToQuerystring(this.filters),
        }),
        style: new Style({
          image: new Circle({
            radius: 7,
            fill: new Fill({color: "red"}),
          }),
        }),
        opacity: this.dataLayerOpacity,
        minZoom: this.layerSwitchZoomLevel,
      });
    },
    createAggregatedDataLayer: function (): VectorTileLayer<Feature> {
      return new VectorTileLayer({
        source: new VectorTileSource({
          format: new MVT(),
          url:
              this.apiEndpoints.tileServerAggregatedUrlTemplate +
              "?" +
              filtersToQuerystring(this.filters),
        }),
        style: this.aggregatedDataLayerStyleFunction,
        opacity: this.dataLayerOpacity,
        maxZoom: this.layerSwitchZoomLevel,
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
    this.map = this.createBasicMap();

    // Prepare popup
    this.popup.setElement(this.$refs["popup-root"] as HTMLElement);
    this.map.addOverlay(this.popup as Overlay);

    this.replaceDataLayers();

    this.map.on("click", (evt) => {
      if (
          this.map &&
          this.map.getView().getZoom()! >= this.layerSwitchZoomLevel
      ) {
        const features = this.map.getFeaturesAtPixel(evt.pixel);

        const clickedFeaturesData = features.map((f) => {
          const properties = f.getProperties();
          return {
            gbifId: properties["gbif_id"],
            scientificName: properties["scientific_name"],
            url: this.apiEndpoints.observationDetailsUrlTemplate.replace(
                "{stable_id}",
                properties["stable_id"]
            ).replace("{origin}", window.location.pathname),
          };
        });

        const clickedFeaturesHtmlList = clickedFeaturesData.map((f) => {
          return `<li><a href="${f.url}" target="_blank">${f.gbifId}</a> <i>${f.scientificName}</i></li>`;
        });

        // Hide previously opened
        if (this.popover !== null) {
          this.popover.hide();
        }

        if (clickedFeaturesData.length > 0) {
          this.popup.setPosition(evt.coordinate);
          this.popover = new Popover(this.popup.getElement() as HTMLElement, {
            html: true,
            content:
                "<ul class='list-unstyled'>" +
                clickedFeaturesHtmlList.join("") +
                "</ul>",
          });
          this.popover.show();
        }
      }
    });
  },
});
</script>
