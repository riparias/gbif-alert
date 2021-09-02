import Vue from "vue";
import OccurrencesMap from "./OccurrencesMap.vue";

declare const ripariasConfig: Object;

new Vue({
  el: "#app",
  components: {
    OccurrencesMap,
  },
  delimiters: ["[[", "]]"],
  data: {
    frontendConfig: ripariasConfig,
  },
});
