import { defineStore } from "pinia";
import { getNavConfig } from "../utils/navConfig";

// Client-side, reactive view of the per-user notification dots shown in the
// navbar. The nav config injected by Django is a snapshot taken at page load
// and stays frozen for the whole SPA session, so components must not read the
// dots from it directly: this store seeds itself from that snapshot, then keeps
// itself up to date as the user navigates (see refreshStatus()).

interface UserStatus {
    hasUnseenNews: boolean;
    hasAlertsWithUnseenObservations: boolean;
}

export const useUserStore = defineStore("user", {
    state: (): UserStatus => {
        const { user } = getNavConfig();
        return {
            hasUnseenNews: user.hasUnseenNews,
            hasAlertsWithUnseenObservations: user.hasAlertsWithUnseenObservations,
        };
    },
    actions: {
        // The news page marks itself as visited server-side; no need to ask the
        // server about something we already know.
        markNewsAsSeen(): void {
            this.hasUnseenNews = false;
        },

        // Whether observations are still unseen depends on server-side state we
        // cannot derive here (an alert can hold thousands of observations), so
        // ask. Best-effort: on failure the dots simply keep their old value.
        async refreshStatus(): Promise<void> {
            try {
                const resp = await fetch("/api/v2/spa/user-status/");
                if (!resp.ok) return;
                const status: UserStatus = await resp.json();
                this.hasUnseenNews = status.hasUnseenNews;
                this.hasAlertsWithUnseenObservations = status.hasAlertsWithUnseenObservations;
            } catch {
                /* non-fatal */
            }
        },
    },
});
