import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";

export const routes: RouteRecordRaw[] = [
    // TEMPORARY: /new/ prefix is a dev scaffold served by new_spa_dev Django view.
    // Route is replaced by the real path in step 2.13.
    { path: "/new/", component: IndexPage },
];
