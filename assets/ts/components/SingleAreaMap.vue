<template>
    <h2>{{areaName}}</h2>
    <div ref="mapRoot" :style="{ width: props.mapWidth, height: props.mapHeight }"></div>
    <h3>Delete button</h3>
</template>

<script setup lang="ts">
import {onMounted, ref} from "vue";
import Map from "ol/Map";
import {osmHotSource} from "../map_config";
import {View} from "ol";
import TileLayer from "ol/layer/Tile";
import VectorSource from "ol/source/Vector";
import {GeoJSON} from "ol/format";
import VectorLayer from "ol/layer/Vector";
import {Stroke, Style} from "ol/style";
import axios from "axios";

const mapRoot = ref(null as HTMLElement | null);

interface Props {
  areasUrlTemplate: string
  areaId: number
  mapWidth?: string
  mapHeight?: string
}

const props = withDefaults(defineProps<Props>(), {
  mapWidth: "320px",
  mapHeight: "240px",
});

const initBaseMap = function (target: HTMLElement) {
  return new Map({
    target: target,
    layers: [new TileLayer({source: osmHotSource})],
    view: new View({
      center: [0, 0],
      zoom: 2,
    }),
  });
}

const loadAreaDetails = function (areaId: number, map: Map) {
    // Get the details about the area, populate map and the areaName ref
    axios
        .get(props.areasUrlTemplate.replace("{id}", areaId.toString()))
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

              map.addLayer(vectorLayer);
              map.getView().fit(vectorSource.getExtent());

              areaName.value = response.data["features"][0]["properties"]["name"];
            });
    areaName.value = "test";
}

const areaName = ref("");

onMounted(() => {
    const map = initBaseMap(mapRoot.value as HTMLElement);
    loadAreaDetails(props.areaId, map);
})
</script>
