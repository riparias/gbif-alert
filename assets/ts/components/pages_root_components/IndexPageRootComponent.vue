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
              :button-label-singular="$t('message.basisOfRecord')"
              :button-label-suffix-plural="$t('message.xSelectedBasisOfRecord')"
              :no-selection-button-label="$t('message.allBasisOfRecord')"
              :modal-title="$t('message.basisOfRecordToInclude')"
              :entries="availableBasisOfRecordAsDataRows"
              :selector-columns-config="[
                  {label: $t('message.name'), dataIndex: 0}
              ]"
              :label-index="0"
              :initially-selected-entries-ids="filters.basisOfRecordIds"
              @entries-changed="changeSelectedBasisOfRecord"
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

          <div class="mx-2 d-flex align-items-center" v-if="(filters.areaIds?.length ?? 0) > 0">
            <label class="me-1 text-nowrap">{{ $t('message.areaFilterMode') }}:</label>
            <select v-model="filters.areaFilterMode" class="form-select form-select-sm">
              <option value="inside">{{ $t('message.areaFilterModeInside') }}</option>
              <option value="approaching">{{ $t('message.areaFilterModeApproaching') }}</option>
              <option value="both">{{ $t('message.areaFilterModeBoth') }}</option>
            </select>
          </div>

          <div class="mx-2 d-flex align-items-center"
               v-if="(filters.areaIds?.length ?? 0) > 0 && (filters.areaFilterMode === 'approaching' || filters.areaFilterMode === 'both')">
            <label class="me-1 text-nowrap">{{ $t('message.approachingDistanceKm') }}:</label>
            <input type="number" v-model.number="localApproachingDistanceKm"
                   @input="debouncedUpdateApproachingDistance && debouncedUpdateApproachingDistance(localApproachingDistanceKm)"
                   class="form-control form-control-sm" style="width: 90px;"
                   min="0.1" max="50" step="0.1">
          </div>

          <Filter-Selector
              v-if="showInitialDataImportFilter"
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
              @entries-changed="changeSelectedInitialDataImport "
          ></Filter-Selector>

          <div class="mx-2 d-flex align-items-center">
            <label class="me-1 text-nowrap">{{ $t('message.verificationFilter') }}:</label>
            <select v-model="filters.verifiedFilter" class="form-select form-select-sm">
              <option value="all">{{ $t('message.all') }}</option>
              <option value="verified">{{ $t('message.verifiedOnly') }}</option>
              <option value="unverified">{{ $t('message.unverifiedOnly') }}</option>
            </select>
          </div>

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
  BasisOfRecordInformation,
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
import {dateTimeToFilterParam, prepareAreasData, prepareBasisOfRecordData, prepareDatasetsData, prepareSpeciesData} from "../../helpers";

declare const gbifAlertConfig: FrontEndConfig;
declare const initialFilters: DashboardFilters;

interface IndexPageRootComponentData {
  frontendConfig: FrontEndConfig;
  availableSpecies: SpeciesInformation[];
  availableDatasets: DatasetInformation[];
  availableBasisOfRecord: BasisOfRecordInformation[];
  availableAreas: AreaInformation[];
  availableDataImports: DataImportInformation[];
  filters: DashboardFilters;
  localApproachingDistanceKm: number | null;
  debouncedUpdateDateFilters: DebouncedFunc<(range: DateRange) => void> | undefined;
  debouncedUpdateApproachingDistance: DebouncedFunc<(val: number | null) => void> | undefined;
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
      availableBasisOfRecord: [],
      availableAreas: [],
      availableDataImports: [],

      filters: {
        speciesIds: initialFilters.speciesIds ?? [],
        datasetsIds: initialFilters.datasetsIds ?? [],
        basisOfRecordIds: initialFilters.basisOfRecordIds ?? [],
        startDate: initialFilters.startDate ?? null,
        endDate: initialFilters.endDate ?? null,
        areaIds: initialFilters.areaIds ?? [],
        status: initialFilters.status,
        initialDataImportIds: initialFilters.initialDataImportIds ?? [],
        verifiedFilter: (initialFilters.verifiedFilter ?? 'all') as 'all' | 'verified' | 'unverified',
        areaFilterMode: (initialFilters.areaFilterMode ?? 'inside') as 'inside' | 'approaching' | 'both',
        approachingDistanceKm: initialFilters.approachingDistanceKm ?? null,
      },

      localApproachingDistanceKm: initialFilters.approachingDistanceKm ?? null,

      debouncedUpdateDateFilters: undefined,
      debouncedUpdateApproachingDistance: undefined,
    };
  },
  computed: {
    availableSpeciesAsDataRows: function (): DataRow[] {
      return prepareSpeciesData(this.availableSpecies);
    },
    availableDatasetsAsDataRows: function (): DataRow[] {
      return prepareDatasetsData(this.availableDatasets);
    },
    availableBasisOfRecordAsDataRows: function (): DataRow[] {
      return prepareBasisOfRecordData(this.availableBasisOfRecord);
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
    showInitialDataImportFilter: function (): boolean {
      return (initialFilters.initialDataImportIds?.length ?? 0) > 0;
    },
  },
  created() {
    // Approach stolen  from: https://dmitripavlutin.com/vue-debounce-throttle/
    this.debouncedUpdateDateFilters = debounce((range) => {
      this.filters.startDate = dateTimeToFilterParam(range.start);
      this.filters.endDate = dateTimeToFilterParam(range.end);
    }, 300);
    this.debouncedUpdateApproachingDistance = debounce((val: number | null) => {
      this.filters.approachingDistanceKm = val;
    }, 500);
  },
  beforeUnmount() {
    if (this.debouncedUpdateDateFilters) {
      this.debouncedUpdateDateFilters.cancel();
    }
    if (this.debouncedUpdateApproachingDistance) {
      this.debouncedUpdateApproachingDistance.cancel();
    }
  },
  watch: {
    'filters.areaFilterMode'(newMode: string) {
      if ((newMode === 'approaching' || newMode === 'both') && this.localApproachingDistanceKm === null) {
        this.localApproachingDistanceKm = 5;
        this.filters.approachingDistanceKm = 5;
      }
    },
  },
  methods: {
    // TODO: remove duplication, original in helpers.ts
    scientificNameFormatter: function (_rawValue: string | number, highlightedValue: string): string {
      return `<i>${highlightedValue}</i>`;
    },
    // TODO: remove duplication, original in helpers.ts
    gbifTaxonKeyFormatter: function (rawValue: string | number, highlightedValue: string): string {
      return `<a href="https://www.gbif.org/species/${rawValue}" target="_blank">${highlightedValue}</a>`;
    },
    gbifDatasetKeyFormatter: function (rawValue: string | number, highlightedValue: string): string {
      return `<a class="small" href="https://www.gbif.org/dataset/${rawValue}" target="_blank">${highlightedValue}</a>`;
    },
    changeSelectedSpecies: function (speciesIds: number[]) {
      this.filters.speciesIds = speciesIds;
    },
    changeSelectedDatasets: function (datasetsIds: number[]) {
      this.filters.datasetsIds = datasetsIds;
    },
    changeSelectedBasisOfRecord: function (basisOfRecordIds: number[]) {
      this.filters.basisOfRecordIds = basisOfRecordIds;
    },
    changeSelectedAreas: function (areasIds: number[]) {
      this.filters.areaIds = areasIds;
      // Reset proximity settings when areas are cleared
      if (areasIds.length === 0) {
        this.filters.areaFilterMode = 'inside';
        this.filters.approachingDistanceKm = null;
        this.localApproachingDistanceKm = null;
        if (this.debouncedUpdateApproachingDistance) {
          this.debouncedUpdateApproachingDistance.cancel();
        }
      }
    },
    changeSelectedInitialDataImport: function (dataImportsIds: number[]) {
      this.filters.initialDataImportIds = dataImportsIds;
    },
    populateAvailableDatasets: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.datasetsListUrl)
          .then((response) => {
            this.availableDatasets = response.data;
          });
    },
    populateAvailableBasisOfRecord: function () {
      axios
          .get(this.frontendConfig.apiEndpoints.basisOfRecordListUrl)
          .then((response) => {
            this.availableBasisOfRecord = response.data;
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
    this.populateAvailableBasisOfRecord();
    this.populateAvailableAreas();
    this.populateAvailableDataImports();
  },
});
</script>
