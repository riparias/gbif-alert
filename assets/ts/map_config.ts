import TileLayer from "ol/layer/Tile";
import StadiaMaps from 'ol/source/StadiaMaps.js';
import OSM from "ol/source/OSM";
import XYZ from "ol/source/XYZ";
import {BaseLayerEntry} from "./interfaces";

export const osmHotSource = new OSM({
        url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",}
)

export const baseLayers = [
  {
    name: "toner",
    layer: new TileLayer({ source: new StadiaMaps({ layer: "stamen_toner" }) }),
  },
  {
    name: "osmHot",
    layer: new TileLayer({
      source: osmHotSource
    }),
  },
  {
    name: "esriImagery",
    layer: new TileLayer({
      source: new XYZ({
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        maxZoom: 19,
      }),
    }),
  },
] as BaseLayerEntry[];
