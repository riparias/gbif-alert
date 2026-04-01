import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";
import UserAlertsPage from "../pages/UserAlertsPage.vue";

export const routes: RouteRecordRaw[] = [
    { path: "/", component: IndexPage },
    { path: "/my-alerts", component: UserAlertsPage },
];
