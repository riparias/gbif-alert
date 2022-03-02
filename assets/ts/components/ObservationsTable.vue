<template>
  <div id="table-outer">
    <table
      class="table table-striped table-sm table-hover small"
      id="riparias-observations-table"
    >
      <thead class="thead-dark">
        <tr>
          <th
            :class="{ 'text-primary': sortBy === col.sortId }"
            v-for="col in cols"
            scope="col"
          >
            <span @click="changeSort(col.sortId)">{{ col.label }}</span>
          </th>
        </tr>
      </thead>
      <Observation-table-page
        :observations="observations"
        :observation-page-url-template="observationPageUrlTemplate"
      ></Observation-table-page>
    </table>
    <p class="text-center">
      <button
        type="button"
        :disabled="!hasPreviousPage"
        class="btn btn-outline-primary btn-sm"
        @click="currentPage -= 1"
      >
        Previous
      </button>
      Page {{ currentPage }} / {{ lastPage }}
      <button
        type="button"
        :disabled="!hasNextPage"
        class="btn btn-outline-primary btn-sm"
        @click="currentPage += 1"
      >
        Next
      </button>
    </p>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { DashboardFilters } from "../interfaces";
import axios from "axios";
import ObservationTablePage from "./ObservationTablePage.vue";
import { filtersToQuerystring } from "../helpers";

interface ColDefinition {
  sortId: string | null;
  label: string;
}

declare interface ObservationsTableData {
  currentPage: number;
  firstPage: number | null;
  lastPage: number;
  totalObservationsCount: number | null;
  sortBy: string;
  observations: [];
  cols: ColDefinition[];
}

export default defineComponent({
  name: "ObservationsTable",
  components: { ObservationTablePage },
  props: {
    filters: {
      type: Object as () => DashboardFilters,
      required: true,
    },
    observationsJsonUrl: {
      type: String,
      required: true,
    },
    observationPageUrlTemplate: String,
    pageSize: {
      type: Number,
      default: 20,
    },
  },
  watch: {
    filters: {
      deep: true,
      immediate: true,
      handler: function () {
        this.currentPage = 1;
        this.loadObservations(
          this.filters,
          this.sortBy,
          this.pageSize,
          this.currentPage
        );
      },
    },
    currentPage: function () {
      this.loadObservations(
        this.filters,
        this.sortBy,
        this.pageSize,
        this.currentPage
      );
    },
    sortBy: function () {
      this.loadObservations(
        this.filters,
        this.sortBy,
        this.pageSize,
        this.currentPage
      );
    },
  },
  methods: {
    changeSort: function (newSort: string | null) {
      if (newSort != null) {
        this.sortBy = newSort;
      }
    },
    loadObservations: function (
      filters: DashboardFilters,
      orderBy: string,
      pageSize: number,
      pageNumber: number
    ) {
      let params = { ...filters } as any;
      params.order = orderBy;
      params.limit = pageSize;
      params.page_number = pageNumber;

      axios
        .get(this.observationsJsonUrl, {
          params: params,
          paramsSerializer: filtersToQuerystring,
        })
        .then((response) => {
          this.observations = response.data.results;
          this.firstPage = response.data.firstPage;
          this.lastPage = response.data.lastPage;
          this.totalObservationsCount = response.data.totalResultsCount;
        });

      params.order = orderBy;
      params.limit = pageSize;
      params.page_number = pageNumber;
    },
  },
  computed: {
    hasPreviousPage: function (): boolean {
      return this.currentPage > 1;
    },
    hasNextPage: function (): boolean {
      return this.currentPage < this.lastPage;
    },
  },
  data: function (): ObservationsTableData {
    return {
      currentPage: 1,
      firstPage: 1,
      lastPage: 1,
      totalObservationsCount: null,
      sortBy: "id",
      observations: [],

      cols: [
        // sortId: must match django QS filter (null = non-sortable), label: what's displayed in header
        // Beware: the actual data display occurs in ObservationsTablePage component, make sure the header and data shown
        // stay synchronised
        { sortId: null, label: "" },
        { sortId: "gbif_id", label: "GBIF Id" },
        { sortId: null, label: "Lat" },
        { sortId: null, label: "Lon" },
        { sortId: null, label: "Date" },
        { sortId: "species__name", label: "Species" },
        { sortId: "source_dataset__name", label: "Dataset" },
      ],
    };
  },
});
</script>
