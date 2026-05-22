import { ref } from "vue";
import { defineStore } from "pinia";

export const useResultsStore = defineStore("results", () => {
    const observationCount = ref(0);
    const speciesCount = ref(0);
    const datasetsCount = ref(0);
    const loading = ref(false);

    // Bumped whenever an observation's seen/unseen status changes (currently:
    // when the detail drawer closes, since opening it auto-marks the obs as
    // seen server-side, and the drawer also exposes a "mark as not viewed"
    // action). Consumers that display data derived from seen/unseen state
    // watch this and re-fetch.
    const statusEpoch = ref(0);
    function bumpStatusEpoch() {
        statusEpoch.value += 1;
    }

    return {
        observationCount,
        speciesCount,
        datasetsCount,
        loading,
        statusEpoch,
        bumpStatusEpoch,
    };
});
