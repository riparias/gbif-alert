import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";

export const routes: RouteRecordRaw[] = [
    { path: "/", component: IndexPage },
];
