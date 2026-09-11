import { ref, watch, markRaw } from "vue";
import TileLayer from "ol/layer/Tile";
import TileWMS from "ol/source/TileWMS";
import XYZ from "ol/source/XYZ";
import type { Map as OLMap } from "ol";
import { getNavConfig, type BaseLayerConfig } from "../utils/navConfig";

// Used when the instance has no base layer configured at all (an operator can
// delete every row in the admin). A map with no background is unreadable, so
// we keep one keyless layer built in rather than render nothing.
const FALLBACK_LAYER: BaseLayerConfig = {
    id: -1,
    name: "OSM HOT",
    type: "xyz",
    url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
    wmsLayers: "",
    attribution: "OpenStreetMap contributors, tiles by Humanitarian OpenStreetMap Team",
    maxZoom: 19,
};

export function getBaseLayers(): BaseLayerConfig[] {
    const configured = getNavConfig().map?.baseLayers;
    return configured && configured.length > 0 ? configured : [FALLBACK_LAYER];
}

export function makeBaseLayer(layer: BaseLayerConfig): TileLayer<any> {
    const attributions = layer.attribution ? [layer.attribution] : undefined;

    if (layer.type === "wms") {
        return new TileLayer({
            source: new TileWMS({
                url: layer.url,
                params: { LAYERS: layer.wmsLayers, TILED: true },
                attributions,
            }),
        });
    }

    return new TileLayer({
        source: new XYZ({ url: layer.url, maxZoom: layer.maxZoom, attributions }),
    });
}

/** The layer maps open with: the first one the operator put in the picker. */
export function makeDefaultBaseLayer(): TileLayer<any> {
    return makeBaseLayer(getBaseLayers()[0]);
}

/**
 * Composable that manages the base tile layer of an OpenLayers map.
 *
 * Usage:
 *   const { baseLayers, selectedBaseLayerId, attachToMap } = useBaseLayer();
 *   // In onMounted, after creating olMap:
 *   attachToMap(olMap);
 */
export function useBaseLayer() {
    const baseLayers = getBaseLayers();
    const selectedBaseLayerId = ref<number>(baseLayers[0].id);

    function attachToMap(olMap: OLMap): void {
        watch(selectedBaseLayerId, (newId) => {
            const layer = baseLayers.find((l) => l.id === newId);
            if (!layer) {
                return;
            }
            const layers = olMap.getLayers();
            layers.removeAt(0);
            layers.insertAt(0, markRaw(makeBaseLayer(layer)));
        });
    }

    return { baseLayers, selectedBaseLayerId, attachToMap };
}
