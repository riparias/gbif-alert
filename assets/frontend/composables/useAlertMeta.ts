import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import type { components } from "../types/api";
import { useDisplayLabels } from "./useDisplayLabels";

type AlertOut = components["schemas"]["AlertOut"];

const SPECIES_COLLAPSE_THRESHOLD = 4;

export function useAlertMeta(alert: () => AlertOut) {
    const { t } = useI18n();
    const { areaName } = useDisplayLabels();

    const speciesExpanded = ref(false);

    const tooManySpecies = computed(
        () => alert().speciesDetails.length > SPECIES_COLLAPSE_THRESHOLD
    );

    const visibleSpecies = computed(() =>
        tooManySpecies.value && !speciesExpanded.value
            ? alert().speciesDetails.slice(0, SPECIES_COLLAPSE_THRESHOLD)
            : alert().speciesDetails
    );

    const areaDescription = computed(() => {
        // areaNames was dropped from AlertOut (N5); derive from areaIds.
        const names = alert().areaIds.map((id) => areaName(id)).filter(Boolean);
        if (names.length === 0) return "";
        const quoted = names.map((n) => `'${n}'`);
        const areas =
            quoted.length === 1
                ? quoted[0]
                : quoted.slice(0, -1).join(", ") + t("message.areaListJoiner") + quoted[quoted.length - 1];
        const mode = alert().areaFilterMode;
        const dist = alert().approachingDistanceKm;
        if (mode === "inside") return t("message.areaDescriptionInside", { areas });
        if (mode === "approaching") return t("message.areaDescriptionApproaching", { dist, areas });
        return t("message.areaDescriptionBoth", { dist, areas });
    });

    return { speciesExpanded, tooManySpecies, visibleSpecies, areaDescription, SPECIES_COLLAPSE_THRESHOLD };
}
