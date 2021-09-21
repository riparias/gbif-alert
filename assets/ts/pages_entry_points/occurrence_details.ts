import { createApp } from "vue";
import SingleOccurrenceMap from "../components/SingleOccurrenceMap.vue";

const app = createApp({
  components: {
    SingleOccurrenceMap,
  },
  delimiters: ["[[", "]]"],
});

app.mount("#app");
