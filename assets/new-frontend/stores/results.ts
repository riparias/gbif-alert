import { ref } from "vue";
import { defineStore } from "pinia";

export const useResultsStore = defineStore("results", () => {
    const observationCount = ref(0);
    const loading = ref(false);
    return { observationCount, loading };
});
