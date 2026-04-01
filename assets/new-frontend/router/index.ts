import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";
import UserAlertsPage from "../pages/UserAlertsPage.vue";
import AlertFormPage from "../pages/AlertFormPage.vue";

export const routes: RouteRecordRaw[] = [
    { path: "/", component: IndexPage },
    { path: "/my-alerts", component: UserAlertsPage },
    { path: "/new-alert", component: AlertFormPage },
    { path: "/edit-alert/:alertId", component: AlertFormPage },
];
