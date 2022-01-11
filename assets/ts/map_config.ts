import TileLayer from "ol/layer/Tile";
import Stamen from "ol/source/Stamen";
import OSM from "ol/source/OSM";
import XYZ from "ol/source/XYZ";
import { BaseLayerEntry } from "./interfaces";

export const baseLayers = [
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
