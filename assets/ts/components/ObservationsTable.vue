<template>
  <div id="table-outer">
    <table
        class="table table-striped table-sm table-hover small"
        id="gbif-alert-observations-table"
    >
      <thead class="thead-dark">
      <tr>
        <th
            :class="{ 'text-primary': sortBy === col.sortId }"
            v-for="col in cols"
            scope="col"
        >
          <span @click="changeSort(col.sortId)">{{ col.label }}</span>
          <i v-if="sortBy === col.sortId"
             :class="sortDirection === 'asc' ? 'bi bi-caret-up-fill' : 'bi bi-caret-down-fill'"></i>
          <i v-else-if="col.sortId != null" class="bi bi-caret-up"></i>
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
          class="btn btn-outline-primary btn-sm mx-1"
          @click="currentPage = 1"
      >
        <i class="bi bi-chevron-double-left"></i>
      </button>

      <button
          type="button"
          :disabled="!hasPreviousPage"
          class="btn btn-outline-primary btn-sm mx-1"
          @click="currentPage -= 1"
      >
        <i class="bi bi-chevron-left"></i>
      </button>
      {{ $t("message.page") }} {{ currentPage }} / {{ lastPage }}
      <button
          type="button"
          :disabled="!hasNextPage"
          class="btn btn-outline-primary btn-sm mx-1"
          @click="currentPage += 1"
      >
        <i class="bi bi-chevron-right"></i>
      </button>

      <button
          type="button"
          :disabled="!hasNextPage"
          class="btn btn-outline-primary btn-sm mx-1"
          @click="currentPage = lastPage"
      >
        <i class="bi bi-chevron-double-right"></i>
      </button>
    </p>
  </div>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {DashboardFilters} from "../interfaces";
import axios from "axios";
import ObservationTablePage from "./ObservationTablePage.vue";

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
  sortDirection: string;
  observations: [];
  cols: ColDefinition[];
}

export default defineComponent({
  name: "ObservationsTable",
  components: {ObservationTablePage},
  props: {
    filters: {
      type: Object as () => DashboardFilters,
      required: true,
    },
    observationsJsonUrl: {
      type: String,
      required: true,
    },
    observationPageUrlTemplate: {type: String, required: true},
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
            this.sortDirection,
            this.pageSize,
            this.currentPage
        );
      },
    },
    currentPage: function () {
      this.loadObservations(
          this.filters,
          this.sortBy,
          this.sortDirection,
          this.pageSize,
          this.currentPage
      );
    },
    sortBy: function () {
      this.loadObservations(
          this.filters,
          this.sortBy,
          this.sortDirection,
          this.pageSize,
          this.currentPage
      );
    },
    sortDirection: function () {
      this.loadObservations(
          this.filters,
          this.sortBy,
          this.sortDirection,
          this.pageSize,
          this.currentPage
      );
    },
  },
  methods: {
    changeSort: function (newSort: string | null) {
      if (newSort != null) {
        if (newSort === this.sortBy) {
          // Same column, change direction
          this.sortDirection =
              this.sortDirection === "asc" ? "desc" : "asc";
        } else {
          // New column, sort ascending
          this.sortBy = newSort;
          this.sortDirection = "asc";
        }
      }
    },
    loadObservations: function (
        filters: DashboardFilters,
        orderBy: string,
        orderDirection: string,
        pageSize: number,
        pageNumber: number
    ) {
      let params = {...filters} as any;
      if (orderDirection === 'asc') {
        params.order = orderBy;
      } else {
        params.order = '-' + orderBy;
      }
      params.limit = pageSize;
      params.page_number = pageNumber;

      axios
          .get(this.observationsJsonUrl, {
            params: params,
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
      sortBy: "date",
      sortDirection: "desc",
      observations: [],

      cols: [
        // sortId: must match django QS filter (null = non-sortable), label: what's displayed in header
        // Beware: the actual data display occurs in ObservationsTablePage component, make sure the header and data shown
        // stay synchronised
        //
        // If changing/adding fields there, please also consider adding them to the email notifications
        // (alert_notification.html)
        {sortId: null, label: ""},
        {sortId: "gbif_id", label: this.$t("message.gbifId")},
        {sortId: null, label: this.$t("message.coordinates")},
        {sortId: "date", label: this.$t("message.date")},
        {sortId: "species__name", label: this.$t("message.species")},
        {sortId: "source_dataset__name", label: this.$t("message.dataset")},
      ],
    };
  },
});
</script>
