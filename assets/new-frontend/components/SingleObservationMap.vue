<script setup lang="ts">
import { ref, onMounted, markRaw } from "vue";
import { Map as OLMap, Feature, View } from "ol";
import { fromLonLat } from "ol/proj";
import TileLayer from "ol/layer/Tile";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import OSM from "ol/source/OSM";
import { Circle as CircleGeom } from "ol/geom";
import { Style, Fill, Stroke } from "ol/style";
import { ScaleLine } from "ol/control";
import "ol/ol.css";

const props = withDefaults(
    defineProps<{
        lat: number;
        lon: number;
        coordinateUncertaintyInMeters?: number | null;
    }>(),
    { coordinateUncertaintyInMeters: null }
);

// Exact uncertainty -> teal circle; unknown -> 100 m red circle as convention
const radiusMeters = props.coordinateUncertaintyInMeters ?? 100;
const fillColor =
    props.coordinateUncertaintyInMeters != null
        ? "rgba(0,165,141,0.8)"
        : "rgba(255,0,0,0.8)";

const mapEl = ref<HTMLElement | null>(null);

onMounted(() => {
    const center = fromLonLat([props.lon, props.lat]);
    const circleGeom = new CircleGeom(center, radiusMeters);

    const feature = new Feature({ geometry: circleGeom });
    const vectorLayer = markRaw(
        new VectorLayer({
            source: new VectorSource({ features: [feature] }),
            style: new Style({
                fill: new Fill({ color: fillColor }),
                stroke: new Stroke({ width: 1.25 }),
            }),
        })
    );

    const map = markRaw(
        new OLMap({
            target: mapEl.value!,
            layers: [
                new TileLayer({
                    source: new OSM({
                        url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
                    }),
                }),
                vectorLayer,
            ],
            view: new View({ center, zoom: 12 }),
        })
    );

    map.addControl(new ScaleLine());

    // Fit to the circle with one zoom level of padding
    const view = map.getView();
    view.fit(circleGeom, { maxZoom: 20 });
    view.setZoom(view.getZoom()! - 1);
});
</script>

<template>
    <div ref="mapEl" class="single-obs-map" />
</template>

<style scoped>
.single-obs-map {
    width: 100%;
    height: 320px;
}
</style>
