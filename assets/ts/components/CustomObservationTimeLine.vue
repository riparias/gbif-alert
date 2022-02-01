<template>
  <bar-chart
    :bar-data="preparedHistogramData"
    :data-loaded="dataLoaded"
    @selectedRangeUpdated="selectedRange = $event"
  ></bar-chart>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import {
  DashboardFilters,
  DateRange,
  PreparedHistogramDataEntry,
} from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";
import BarChart from "./BarChart.vue";
import { DateTime } from "luxon";

interface HistogramDataEntry {
  // As received from the server
  year: number;
  month: number;
  count: number;
}

interface CustomObservationsTimeLineData {
  histogramDataFromServer: HistogramDataEntry[];
  dataLoaded: boolean;
  selectedRange: DateRange;
}

const range = (start: number, end: number): number[] =>
  Array.from({ length: end - start }, (v, k) => k + start);

export default defineComponent({
  name: "CustomObservationsTimeLine",
  components: {
    BarChart,
  },
  props: {
    histogramDataUrl: {
      type: String,
      required: true,
    },
    filters: {
      type: Object as () => DashboardFilters,
      required: true,
    },
    barsColor: {
      type: String,
      default: "#FC9775",
    },
    chartHeight: {
      type: Number,
      default: 200,
    },
  },
  emits: ["selectedDateRangeUpdated"],
  data: function (): CustomObservationsTimeLineData {
    return {
      histogramDataFromServer: [],
      dataLoaded: false,
      selectedRange: { start: null, end: null },
    };
  },
  computed: {
    preparedHistogramData: function (): PreparedHistogramDataEntry[] {
      return this.histogramDataFromServer.map((e) => {
        return {
          yearMonth: e.year + "-" + e.month,
          count: e.count,
        };
      });
    },
  },
  methods: {
    buildEmptyHistogramArray: function (
      rangeStart: HistogramDataEntry
    ): HistogramDataEntry[] {
      // first entry: first month with data from server
      // Last entry: current month
      let data = [] as HistogramDataEntry[];
      const yearsRange = range(rangeStart.year, DateTime.now().year + 1);
      yearsRange.forEach((currentYear, yearIndex) => {
        const startMonth = yearIndex === 0 ? rangeStart.month : 1;
        const endMonth =
          yearIndex === yearsRange.length - 1 ? DateTime.now().month : 12;

        for (
          let currentMonth = startMonth;
          currentMonth <= endMonth;
          currentMonth++
        ) {
          data.push({
            year: currentYear,
            month: currentMonth,
            count: 0,
          });
        }
      });
      return data;
    },
    loadHistogramData: function (filters: DashboardFilters) {
      this.dataLoaded = false;

      // The histogram has to drop the date filtering parameters
      const strippedFilters = (({ startDate, endDate, ...o }) => o)(filters);

      axios
        .get(this.histogramDataUrl, {
          params: strippedFilters,
          paramsSerializer: filtersToQuerystring,
        })
        .then((response) => {
          if (response.data.length === 0) {
            this.histogramDataFromServer = [];
          } else {
            // Build an empty range (padding)
            let emptyHistogramData = this.buildEmptyHistogramArray(
              response.data[0]
            );

            // Populate it
            response.data.forEach((serverEntry: HistogramDataEntry) => {
              const index = emptyHistogramData.findIndex(function (elem) {
                return (
                  elem.year === serverEntry.year &&
                  elem.month === serverEntry.month
                );
              });
              emptyHistogramData[index].count = serverEntry.count;
            });

            this.histogramDataFromServer = emptyHistogramData;
            this.dataLoaded = true;
          }
        });
    },
  },
  watch: {
    filters: {
      deep: true,
      immediate: true,
      handler: function (val) {
        this.loadHistogramData(val);
      },
    },
    selectedRange: function () {
      this.$emit("selectedDateRangeUpdated", this.selectedRange);
    },
  },
});
</script>
