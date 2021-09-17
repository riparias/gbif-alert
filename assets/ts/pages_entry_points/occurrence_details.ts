import Vue from "vue";
import SingleOccurrenceMap from "../components/SingleOccurrenceMap.vue";

new Vue({
  el: "#app",
  components: {
    SingleOccurrenceMap,
  },
  delimiters: ["[[", "]]"],
});
