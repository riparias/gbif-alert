import * as bootstrap from "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
import SingleObservationMap from "./components/SingleObservationMap.vue";
import DeleteAccountButton from "./components/DeleteAccountButton.vue";
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

(window as any).initObservationDetailsPage = function () {
    createAndMountComponent({components: {SingleObservationMap}}, "#single-observation-app");
};

(window as any).initUserProfilePage = function () {
    createAndMountComponent({components: {DeleteAccountButton}});
};

(window as any).initUserAreasPage = function () {
    createAndMountComponent({components: {UserAreasPageRootComponent}}, "#vue-app");
};
