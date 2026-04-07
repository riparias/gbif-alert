import { type RouteRecordRaw } from "vue-router";
import NotFoundPage from "../pages/NotFoundPage.vue";

// All page components are lazy-loaded so only the current route's code is
// downloaded on the initial page visit. NotFoundPage is kept eager because
// it is trivial (no heavy deps) and must render without a network round-trip.
export const routes: RouteRecordRaw[] = [
    { path: "/", component: () => import("../pages/IndexPage.vue") },
    { path: "/observation/:stableId", redirect: (to) => ({ path: "/", query: { obs: to.params.stableId as string } }) },
    { path: "/my-alerts", component: () => import("../pages/UserAlertsPage.vue") },
    { path: "/new-alert", component: () => import("../pages/AlertFormPage.vue") },
    { path: "/edit-alert/:alertId", component: () => import("../pages/AlertFormPage.vue") },
    { path: "/alert/:alertId", component: () => import("../pages/AlertDetailPage.vue") },
    { path: "/my-custom-areas", component: () => import("../pages/UserAreasPage.vue") },
    { path: "/accounts/signin/", component: () => import("../pages/SignInPage.vue") },
    { path: "/signup", component: () => import("../pages/SignUpPage.vue") },
    { path: "/accounts/password-change/", component: () => import("../pages/PasswordChangePage.vue") },
    { path: "/about-site", component: () => import("../pages/AboutSitePage.vue") },
    { path: "/about-data", component: () => import("../pages/AboutDataPage.vue") },
    { path: "/whats-new", component: () => import("../pages/NewsPage.vue") },
    { path: "/profile", component: () => import("../pages/UserProfilePage.vue") },
    { path: "/:pathMatch(.*)*", component: NotFoundPage },
];
