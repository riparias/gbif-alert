import * as bootstrap from "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
import IndexPageRootComponent from "./components/pages_root_components/IndexPageRootComponent.vue";
import AlertDetailsPageRootComponent from "./components/pages_root_components/AlertDetailsPageRootComponent.vue";
import AlertForm from "./components/AlertForm.vue";
import SingleObservationMap from "./components/SingleObservationMap.vue";
import DeleteAccountButton from "./components/DeleteAccountButton.vue";
import DeleteAlertButton from "./components/DeleteAlertButton.vue";
import {Component, createApp} from "vue";
import {createI18n} from "vue-i18n";
import {messages} from "./translations";
import UserAreasPageRootComponent from "./components/pages_root_components/UserAreasPageRootComponent.vue";

require("bootstrap-icons/font/bootstrap-icons.css");

// Enable bootstrap dropdowns
function initDropDown() {
    const dropdownElementList = [].slice.call(
        document.querySelectorAll(".dropdown-toggle")
    );
    dropdownElementList.map(function (dropdownToggleEl) {
        return new bootstrap.Dropdown(dropdownToggleEl);
    });
}

document.addEventListener("DOMContentLoaded", function (event) {
    initDropDown();
});

// Vue-related stuff
const i18n = createI18n({
    locale: (window as any).LANGUAGE_CODE,
    fallbackLocale: 'en',
    legacy: false,
    messages,
});

function createAndMountComponent(component: Component, rootContainer = "#app") {
    const app = createApp(component);
    app.use(i18n);
    app.config.globalProperties.window = window;
    app.mount(rootContainer);
}

(window as any).initIndexPage = function () {
    createAndMountComponent(IndexPageRootComponent);
};

(window as any).initAlertDetailsPage = function () {
    createAndMountComponent(AlertDetailsPageRootComponent);
    createAndMountComponent({
        components: {
            DeleteAlertButton
        }
    }, "#app-alert-metadata");
};

(window as any).initObservationDetailsPage = function () {
    createAndMountComponent({components: {SingleObservationMap}}, "#single-observation-app");
};

(window as any).initUserProfilePage = function () {
    createAndMountComponent({components: {DeleteAccountButton}});
};

(window as any).initUserAlertsPage = function () {
    createAndMountComponent({components: {DeleteAlertButton}});
};

(window as any).initUserAreasPage = function () {
    createAndMountComponent({components: {UserAreasPageRootComponent}}, "#vue-app");
};

(window as any).initCreateAlertPage = function () {
    createAndMountComponent({components: {AlertForm}});
};

(window as any).initEditAlertPage = function () {
    createAndMountComponent({components: {AlertForm}});
};