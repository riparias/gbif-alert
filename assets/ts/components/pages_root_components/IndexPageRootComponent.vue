<template>
  <div class="row">
    <div class="col-sm my-2">
      <div class="row">
        <div class="col-2 d-flex align-items-center">
          <b>{{ $t("message.filters") }}</b>
        </div>

        <div class="col d-flex align-items-center">
          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.species')"
              :button-label-suffix-plural="$t('message.xSelectedSpecies')"
              :no-selection-button-label="$t('message.allSpecies')"
              :modal-title="$t('message.speciesToInclude')"
              :entries="availableSpeciesAsDataRows"
              :selector-columns-config="[
                  {label: $t('message.scientificName'), dataIndex: 0, formatter: scientificNameFormatter },
                  {label: $t('message.vernacularName'), dataIndex: 1},
                  {label: $t('message.gbifTaxonKey'), dataIndex: 2, formatter: gbifTaxonKeyFormatter }
              ]"
              :label-index="0"
              :initially-selected-entries-ids="filters.speciesIds"
              @entries-changed="changeSelectedSpecies"
          ></Filter-Selector>

          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.dataset')"
              :button-label-suffix-plural="$t('message.xSelectedDatasets')"
              :no-selection-button-label="$t('message.allDatasets')"
              :modal-title="$t('message.datasetsToInclude')"
              :entries="availableDatasetsAsDataRows"
              :selector-columns-config="[
                  {label: $t('message.name'), dataIndex: 0},
                  {label: $t('message.gbifDatasetKey'), dataIndex: 1, formatter: gbifDatasetKeyFormatter }
              ]"
              :label-index="0"
              :initially-selected-entries-ids="filters.datasetsIds"
              @entries-changed="changeSelectedDatasets"
          ></Filter-Selector>

          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.area')"
              :button-label-suffix-plural="$t('message.xSelectedAreas')"
              :no-selection-button-label="$t('message.everywhere')"
              :modal-title="$t('message.restrictToSpecificAreas')"
              :entries="availableAreasAsDataRows"
              :selector-columns-config="[
                  {label: $t('message.name'), dataIndex: 0}
              ]"
              :label-index="0"
              :initially-selected-entries-ids="filters.areaIds"
              @entries-changed="changeSelectedAreas"
          >
              <template v-slot:modal-body-top>
                  <div class="my-2">
                      <i class="bi bi-info-circle"></i>&nbsp;
                      <i18n-t keypath="message.customAreasInfoMessage" tag="false" for="message.customAreasLinkLabel">
                          <a :href="frontendConfig.apiEndpoints.myCustomAreasUrl">{{ $t('message.customAreasLinkLabel') }}</a>
                      </i18n-t>
                  </div>
              </template>
          </Filter-Selector>

          <Filter-Selector
              class="mx-2"
              :button-label-singular="$t('message.initialDataImport')"
              :button-label-suffix-plural="$t('message.xSelectedInitialDataImports')"
              :no-selection-button-label="$t('message.importedAnytime')"
              :modal-title="$t('message.firstImportedDuringDataImports')"
              :entries="availableDataimportsAsDataRows"
              :selector-columns-config="[{label: $t('message.id'), dataIndex: 0}, {label: $t('message.name'), dataIndex: 1}, {label: $t('message.datetimeStart'), dataIndex: 2}]"
              :selector-initial-sort-by="0"
              :selector-initial-sort-direction="'desc'"
              :label-index="0"
              :initially-selected-entries-ids="filters.initialDataImportIds"
              @entries-changed="changeSelectedInitialDataImport"
          ></Filter-Selector>

          <ObservationStatusSelector
              v-if="frontendConfig.authenticatedUser"
              v-model="filters.status"
              :skip-mark-action="true"
              :endpoints-urls="frontendConfig.apiEndpoints"
              :filters="filters"
          ></ObservationStatusSelector>
        </div>
      </div>
    </div>
  </div>
  <Observations
      :frontend-config="frontendConfig"
      :filters="filters"
      @selectedDateRangeUpdated="debouncedUpdateDateFilters"
  ></Observations>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {
  AreaInformation,
  DashboardFilters,
  DataImportInformation,
  DataRow,
  DatasetInformation,
  DateRange,
  FrontEndConfig,
  SpeciesInformation,
} from "../../interfaces";
import axios from "axios";

import FilterSelector from "../FilterSelector.vue";
import ObservationStatusSelector from "../ObservationStatusSelector.vue";
import Observations from "../Observations.vue";
import BootstrapAlert from "../BootstrapAlert.vue";

import {debounce, DebouncedFunc} from "lodash";
import {dateTimeToFilterParam, prepareAreasData, prepareDatasetsData, prepareSpeciesData} from "../../helpers";

declare const gbifAlertConfig: FrontEndConfig;
declare const initialFilters: DashboardFilters;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  availableDatasets: DatasetInformation[];
  availableAreas: AreaInformation[];
  availableDataImports: DataImportInformation[];
  filters: DashboardFilters;
  debouncedUpdateDateFilters: null | DebouncedFunc<(range: DateRange) => void>;
}

export default defineComponent({
  name: "IndexPageRootComponent",

  components: {
    BootstrapAlert,
    Observations,
    ObservationStatusSelector,
    FilterSelector,
  },
  data: function (): IndexPageRootComponentData {
    return {
      frontendConfig: gbifAlertConfig,

      availableSpecies: [],
      availableDatasets: [],
      availableAreas: [],
      availableDataImports: [],

      filters: initialFilters,

      debouncedUpdateDateFilters: null,
    };
  },
  computed: {
    availableSpeciesAsDataRows: function (): DataRow[] {
      return prepareSpeciesData(this.availableSpecies);
    },
    availableDatasetsAsDataRows: function (): DataRow[] {
      return prepareDatasetsData(this.availableDatasets);
    },
    availableAreasAsDataRows: function (): DataRow[] {
      return prepareAreasData(this.availableAreas, this.$t);
    },
    availableDataimportsAsDataRows: function (): DataRow[] {
      return this.availableDataImports
          .map((d) => {
            return {id: d.id, columnData: [d.id, d.name, (new Date(d.startTimestamp)).toLocaleString()]};
          });
    },
  },
  created() {
    // Approach stolen  from: https://dmitripavlutin.com/vue-debounce-throttle/
    this.debouncedUpdateDateFilters = debounce((range) => {
      this.filters.startDate = dateTimeToFilterParam(range.start);
      this.filters.endDate = dateTimeToFilterParam(range.end);
    }, 300);
  },
  beforeUnmount() {
    if (this.debouncedUpdateDateFilters) {
      this.debouncedUpdateDateFilters.cancel();
    }
  },
  methods: {
    // TODO: remove duplication, original in helpers.ts
    scientificNameFormatter: function (rawValue: string, highlightedValue: string): string {
      return `<i>${highlightedValue}</i>`;
    },
    // TODO: remove duplication, original in helpers.ts
    gbifTaxonKeyFormatter: function (rawValue: string, highlightedValue: string): string {
      return `<a href="https://www.gbif.org/species/${rawValue}" target="_blank">${highlightedValue}</a>`;
    },
    gbifDatasetKeyFormatter: function (rawValue: string, highlightedValue: string): string {
      return `<a class="small" href="https://www.gbif.org/dataset/${rawValue}" target="_blank">${highlightedValue}</a>`;
    },
    changeSelectedSpecies: function (speciesIds: Number[]) {
      this.filters.speciesIds = speciesIds;
    },
    changeSelectedDatasets: function (datasetsIds: Number[]) {
      this.filters.datasetsIds = datasetsIds;
    },
    changeSelectedAreas: function (areasIds: Number[]) {
      this.filters.areaIds = areasIds;
    },
    changeSelectedInitialDataImport: function (dataImportsIds: Number[]) {
      this.filters.initialDataImportIds = dataImportsIds;
    },
    populateAvailableDatasets: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.datasetsListUrl)
          .then((response) => {
            this.availableDatasets = response.data;
          });
    },
    populateAvailableSpecies: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.speciesListUrl)
          .then((response) => {
            this.availableSpecies = response.data;
          });
    },
    populateAvailableAreas: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.areasListUrl)
          .then((response) => {
            this.availableAreas = response.data;
          });
    },
    populateAvailableDataImports: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.dataImportsListUrl)
          .then((response) => {
            this.availableDataImports = response.data;
          });
    },
  },

  mounted: function () {
    this.populateAvailableSpecies();
    this.populateAvailableDatasets();
    this.populateAvailableAreas();
    this.populateAvailableDataImports();
  },
});
</script>
