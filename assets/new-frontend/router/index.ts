import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";
import UserAlertsPage from "../pages/UserAlertsPage.vue";
import AlertFormPage from "../pages/AlertFormPage.vue";
import AlertDetailPage from "../pages/AlertDetailPage.vue";

export const routes: RouteRecordRaw[] = [
    { path: "/", component: IndexPage },
    { path: "/my-alerts", component: UserAlertsPage },
    { path: "/new-alert", component: AlertFormPage },
    { path: "/edit-alert/:alertId", component: AlertFormPage },
    { path: "/alert/:alertId", component: AlertDetailPage },
];
