<script setup lang="ts">
import { ref, onMounted, markRaw } from "vue";
import { fromLonLat } from "ol/proj";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import { Feature } from "ol";
import { Circle as CircleGeom } from "ol/geom";
import { Style, Fill, Stroke } from "ol/style";
import { ScaleLine } from "ol/control";
import BaseMap from "./BaseMap.vue";

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

const baseMapRef = ref<InstanceType<typeof BaseMap> | null>(null);

onMounted(() => {
    const map = baseMapRef.value!.getOlMap()!;
    const center = fromLonLat([props.lon, props.lat]);
    const circleGeom = new CircleGeom(center, radiusMeters);

    map.addLayer(
        markRaw(
            new VectorLayer({
                source: new VectorSource({ features: [new Feature({ geometry: circleGeom })] }),
                style: new Style({
                    fill: new Fill({ color: fillColor }),
                    stroke: new Stroke({ width: 1.25 }),
                }),
            })
        )
    );

    map.addControl(new ScaleLine());

    // Fit the view to the circle with one zoom level of padding
    const view = map.getView();
    view.fit(circleGeom, { maxZoom: 20 });
    view.setZoom(view.getZoom()! - 1);
});
</script>

<template>
    <BaseMap
        ref="baseMapRef"
        height="320px"
        :initial-lon="lon"
        :initial-lat="lat"
        :initial-zoom="12"
    />
</template>
