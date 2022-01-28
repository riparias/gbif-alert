<template>
  <bar-chart :bar-data="preparedHistogramData"></bar-chart>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { DashboardFilters, PreparedHistogramDataEntry } from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";
import BarChart from "./BarChart.vue";

interface HistogramDataEntry {
  // As received from the server
  year: number;
  month: number;
  count: number;
}

interface CustomObservationsTimeLineData {
  histogramDataFromServer: HistogramDataEntry[];
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
  data: function (): CustomObservationsTimeLineData {
    return {
      histogramDataFromServer: [],
    };
  },
  computed: {
    preparedHistogramData: function (): PreparedHistogramDataEntry[] {
      return this.histogramDataFromServer.map((e) => {
        let newEntry = {
          yearMonth: e.year + "-" + e.month,
          count: e.count,
        };
        return newEntry;
      });
    },
  },
  methods: {
    buildEmptyHistogramArray: function (
      rangeStart: HistogramDataEntry,
      rangeEnd: HistogramDataEntry
    ): HistogramDataEntry[] {
      let data = [] as HistogramDataEntry[];
      const yearsRange = range(rangeStart.year, rangeEnd.year + 1);
      yearsRange.forEach((currentYear, yearIndex) => {
        const startMonth = yearIndex === 0 ? rangeStart.month : 1;
        const endMonth =
          yearIndex === yearsRange.length - 1 ? rangeEnd.month : 12;

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
      axios
        .get(this.histogramDataUrl, {
          params: filters,
          paramsSerializer: filtersToQuerystring,
        })
        .then((response) => {
          if (response.data.length === 0) {
            this.histogramDataFromServer = [];
          } else {
            // Build an empty range (padding)
            let emptyHistogramData = this.buildEmptyHistogramArray(
              response.data[0],
              response.data[response.data.length - 1]
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
  },
});
</script>
