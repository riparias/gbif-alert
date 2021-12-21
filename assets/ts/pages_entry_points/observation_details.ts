import { createApp } from "vue";
import SingleObservationMap from "../components/SingleObservationMap.vue";

const app = createApp({
  components: {
    SingleObservationMap,
  },
  delimiters: ["[[", "]]"],
});

app.mount("#app");
