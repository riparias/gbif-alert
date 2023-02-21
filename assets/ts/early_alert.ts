import * as bootstrap from "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
require("bootstrap-icons/font/bootstrap-icons.css");

import IndexPageRootComponent from "./components/pages_root_components/IndexPageRootComponent.vue";
import AlertDetailsPageRootComponent from "./components/pages_root_components/AlertDetailsPageRootComponent.vue";
import SingleObservationMap from "./components/SingleObservationMap.vue";
import DeleteAccountButton from "./components/DeleteAccountButton.vue";

import { Component, createApp } from "vue";

function initDropDown() {
  var dropdownElementList = [].slice.call(
    document.querySelectorAll(".dropdown-toggle")
  );
  dropdownElementList.map(function (dropdownToggleEl) {
    return new bootstrap.Dropdown(dropdownToggleEl);
  });
}

document.addEventListener("DOMContentLoaded", function (event) {
  initDropDown();
});

function createAndMountRootComponent(component: Component) {
  createApp(component).mount("#app");
}

(window as any).initIndexPage = function () {
  createAndMountRootComponent(IndexPageRootComponent);
};

(window as any).initAlertDetailsPage = function () {
  createAndMountRootComponent(AlertDetailsPageRootComponent);
};

(window as any).initObservationDetailsPage = function () {
  createApp({
    components: {
      SingleObservationMap,
    },
  }).mount("#app");
};

(window as any).initUserProfilePage = function () {
  createApp({
    components: {
      DeleteAccountButton
    },
  }).mount("#app");
};
