import { useI18n } from "vue-i18n";
import { useConfirm } from "primevue/useconfirm";
import { useToast } from "primevue/usetoast";
import { useFiltersStore } from "../stores/filters";
import { getCsrf } from "../utils/csrf";
import { filtersToBody } from "../utils/filterParams";

/**
 * "Mark all as viewed" for the observations matching the current filters.
 *
 * Extracted from AlertSidebar because the alert detail page now offers the same
 * action twice: inside the sidebar on a wide screen, and on the mobile bar,
 * where the sidebar is hidden behind a drawer and burying the main triage
 * action in it would defeat the purpose.
 *
 * The work itself is queued server-side, so the toast reports "queued" rather
 * than "done".
 */
export function useMarkAllAsViewed(): { confirmMarkAllAsViewed: () => void } {
    const { t } = useI18n();
    const confirm = useConfirm();
    const toast = useToast();
    const filtersStore = useFiltersStore();

    function confirmMarkAllAsViewed(): void {
        confirm.require({
            message: t("message.markAllAsViewedConfirm"),
            header: t("message.markAllAsViewed"),
            acceptLabel: t("message.yesImSure"),
            rejectLabel: t("message.cancel"),
            accept: async () => {
                const resp = await fetch("/api/v2/observations/mark-as-viewed/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrf(),
                    },
                    body: JSON.stringify(filtersToBody(filtersStore)),
                });
                if (!resp.ok) return;
                toast.add({
                    severity: "success",
                    summary: t("message.markAllAsViewedQueued"),
                    life: 5000,
                });
            },
        });
    }

    return { confirmMarkAllAsViewed };
}
