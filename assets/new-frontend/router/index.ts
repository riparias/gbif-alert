import { type RouteRecordRaw } from "vue-router";
import IndexPage from "../pages/IndexPage.vue";
import UserAlertsPage from "../pages/UserAlertsPage.vue";
import AlertFormPage from "../pages/AlertFormPage.vue";
import AlertDetailPage from "../pages/AlertDetailPage.vue";
import UserAreasPage from "../pages/UserAreasPage.vue";
import SignInPage from "../pages/SignInPage.vue";
import SignUpPage from "../pages/SignUpPage.vue";
import PasswordChangePage from "../pages/PasswordChangePage.vue";
import AboutSitePage from "../pages/AboutSitePage.vue";
import AboutDataPage from "../pages/AboutDataPage.vue";
import NewsPage from "../pages/NewsPage.vue";
import UserProfilePage from "../pages/UserProfilePage.vue";
import NotFoundPage from "../pages/NotFoundPage.vue";

export const routes: RouteRecordRaw[] = [
    { path: "/", component: IndexPage },
    { path: "/observation/:stableId", redirect: (to) => ({ path: "/", query: { obs: to.params.stableId as string } }) },
    { path: "/my-alerts", component: UserAlertsPage },
    { path: "/new-alert", component: AlertFormPage },
    { path: "/edit-alert/:alertId", component: AlertFormPage },
    { path: "/alert/:alertId", component: AlertDetailPage },
    { path: "/my-custom-areas", component: UserAreasPage },
    { path: "/accounts/signin/", component: SignInPage },
    { path: "/signup", component: SignUpPage },
    { path: "/accounts/password-change/", component: PasswordChangePage },
    { path: "/about-site", component: AboutSitePage },
    { path: "/about-data", component: AboutDataPage },
    { path: "/whats-new", component: NewsPage },
    { path: "/profile", component: UserProfilePage },
    { path: "/:pathMatch(.*)*", component: NotFoundPage },
];
