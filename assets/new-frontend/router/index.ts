import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";
import ObservationDetailPage from "../pages/ObservationDetailPage.vue";

export const routes: RouteRecordRaw[] = [
    // TEMPORARY: /new/ prefix is a dev scaffold served by new_spa_dev Django view.
    // Both routes are replaced by their real paths in step 2.13.
    { path: "/new/", component: IndexPage },
    { path: "/new/observation/:stableId", name: "observation-detail", component: ObservationDetailPage },
];
