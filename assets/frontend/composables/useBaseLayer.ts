import { ref, watch, markRaw } from "vue";
import TileLayer from "ol/layer/Tile";
import StadiaMaps from "ol/source/StadiaMaps";
import OSM from "ol/source/OSM";
import XYZ from "ol/source/XYZ";
import type { Map as OLMap } from "ol";

export const BASE_LAYER_OPTIONS = [
    { id: "osmHot", label: "OSM HOT" },
    { id: "toner", label: "Stamen Toner" },
    { id: "esriImagery", label: "ESRI World Imagery" },
] as const;

export function makeBaseLayer(id: string): TileLayer<any> {
    if (id === "toner") {
        return new TileLayer({ source: new StadiaMaps({ layer: "stamen_toner" }) });
    }
    if (id === "esriImagery") {
        return new TileLayer({
            source: new XYZ({
                url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                maxZoom: 19,
            }),
        });
    }
    return new TileLayer({
        source: new OSM({ url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png" }),
    });
}

/**
 * Composable that manages the base tile layer of an OpenLayers map.
 *
 * Usage:
 *   const { selectedBaseLayerId, attachToMap } = useBaseLayer();
 *   // In onMounted, after creating olMap:
 *   attachToMap(olMap);
 */
export function useBaseLayer() {
    const selectedBaseLayerId = ref<string>("osmHot");

    function attachToMap(olMap: OLMap): void {
        watch(selectedBaseLayerId, (newId) => {
            const layers = olMap.getLayers();
            layers.removeAt(0);
            layers.insertAt(0, markRaw(makeBaseLayer(newId)));
        });
    }

    return { selectedBaseLayerId, attachToMap };
}
