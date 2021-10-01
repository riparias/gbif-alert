<template>
  <canvas ref="canvasElem" :height="chartHeight" width="100%"></canvas>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { DashboardFilters } from "../interfaces";
import axios from "axios";
import { filtersToQuerystring } from "../helpers";
import {
  Chart,
  BarController,
  CategoryScale,
  LinearScale,
  BarElement,
  ChartData,
} from "chart.js";

Chart.register(BarController, CategoryScale, LinearScale, BarElement);

interface HistogramDataEntry {
  year: number;
  month: number;
  count: number;
}

interface OccurrencesTimeLineData {
  histogramData: HistogramDataEntry[];
  chart: any; // As of Oct 2021, I get tons of issues when I try to be more detailed here
}

export default defineComponent({
  name: "OccurrencesTimeLine",
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
  data: function (): OccurrencesTimeLineData {
    return {
      histogramData: [],
      chart: null,
    };
  },
  computed: {
    chartData: function (): ChartData {
      const labels = this.histogramData.map(
        (entry: HistogramDataEntry) => entry.year + "-" + entry.month
      );

      const monthData = this.histogramData.map(
        (entry: HistogramDataEntry) => entry.count
      );

      return {
        labels: labels,
        datasets: [
          {
            label: "Occurrences per month",
            backgroundColor: this.barsColor,
            data: monthData,
          },
        ],
      };
    },
  },
  methods: {
    renderHistogram: function () {
      const ctx = this.$refs.canvasElem;
      this.chart = new Chart(ctx, {
        type: "bar",
        data: this.chartData,
      });
    },
    loadHistogramData: function (filters: DashboardFilters) {
      axios
        .get(this.histogramDataUrl, {
          params: filters,
          paramsSerializer: filtersToQuerystring,
        })
        .then((response) => {
          this.histogramData = response.data;
        });
    },
  },
  watch: {
    histogramData: {
      handler: function (val) {
        if (this.chart) {
          this.chart.destroy();
        }
        this.renderHistogram();
      },
    },
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
