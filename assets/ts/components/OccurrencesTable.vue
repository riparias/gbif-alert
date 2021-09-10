<template>
  <div id="table-outer">
    <table class="table table-striped table-sm">
      <thead class="thead-dark">
      <tr>
        <th :class="{ 'text-primary': (sortBy == col.sortId) }" v-for="col in cols" scope="col">
          <span @click="changeSort(col.sortId)">{{ col.label }}</span>
        </th>
      </tr>
      </thead>
      <Occurrence-table-page :occurrences="occurrences"></Occurrence-table-page>
    </table>
    <p class="text-center">
      <button type="button" :disabled="!hasPreviousPage" class="btn btn-outline-primary btn-sm"
              @click="currentPage -= 1">Previous
      </button>
      Page {{ currentPage }} / {{ lastPage }}
      <button type="button" :disabled="!hasNextPage" class="btn btn-outline-primary btn-sm" @click="currentPage += 1">
        Next
      </button>
    </p>
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import {DashboardFilters} from "../interfaces";
import axios from "axios";
import OccurrenceTablePage from "./OccurrenceTablePage.vue";

interface ColDefinition {
  sortId: string | null
  label: string
}

declare interface OccurrencesTableData {
  currentPage: number
  firstPage: number | null
  lastPage: number
  totalOccurrencesCount: number | null
  sortBy: string
  occurrences: []
  cols: ColDefinition[]
}


export default Vue.extend({
  name: "OccurrencesTable",
  components: {OccurrenceTablePage},
  props: {
    'filters': Object as () => DashboardFilters,
    'occurrencesJsonUrl': String,
    'pageSize': {
      type: Number,
      default: 20
    }
  },
  watch: {
    filters: {
      deep: true,
      immediate: true,
      handler: function () {
        this.currentPage = 1;
        this.loadOccurrences(this.filters, this.sortBy, this.pageSize, this.currentPage);
      },
    },
    currentPage: function () {
      this.loadOccurrences(this.filters, this.sortBy, this.pageSize, this.currentPage);
    },
    sortBy: function () {
      this.loadOccurrences(this.filters, this.sortBy, this.pageSize, this.currentPage);
    },
  },
  methods: {
    changeSort: function (newSort: string | null) {
      if (newSort != null) {
        this.sortBy = newSort;
      }
    },
    loadOccurrences: function (filters: DashboardFilters, orderBy: string, pageSize: number, pageNumber: number) {
      let params = {...filters} as any;
      params.order = orderBy;
      params.limit = pageSize;
      params.page_number = pageNumber

      axios.get(this.occurrencesJsonUrl, {params: params}).then(response => {
        this.occurrences = response.data.results;
        this.firstPage = response.data.firstPage;
        this.lastPage = response.data.lastPage - 1;
        this.totalOccurrencesCount = response.data.totalResultsCount
      })

      params.order = orderBy;
      params.limit = pageSize;
      params.page_number = pageNumber;
    }
  },
  computed: {
    hasPreviousPage: function (): boolean {
      return (this.currentPage > 1);
    },
    hasNextPage: function (): boolean {
      return (this.currentPage < this.lastPage);
    },
  },
  data: function (): OccurrencesTableData {
    return {
      currentPage: 1,
      firstPage: 1,
      lastPage: 1,
      totalOccurrencesCount: null,
      sortBy: 'id',
      occurrences: [],

      cols: [
        // sortId: must match django QS filter (null = non-sortable), label: displayed in header
        {'sortId': 'id', 'label': '#',},
        {'sortId': null, 'label': 'Lat',},
        {'sortId': null, 'label': 'Lon',},
        {'sortId': null, 'label': 'Date',},
        {'sortId': 'species__name', 'label': 'Species',},
      ]
    }
  },

})
</script>
