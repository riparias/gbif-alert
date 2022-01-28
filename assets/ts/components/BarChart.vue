<template>
  <svg
    class="d-block mx-auto"
    :width="svgStyle.width"
    :height="svgStyle.height"
  >
    <g
      :transform="`translate(${svgStyle.margin.left}, ${svgStyle.margin.top})`"
    >
      <rect
        class="riparias-bar"
        v-for="(barDataEntry, index) in truncatedBarData"
        :class="{
          selected:
            index >= selectedRangeStartIndex && index <= selectedRangeEndIndex,
        }"
        :key="barDataEntry.yearMonth"
        :x="xScale(barDataEntry.yearMonth)"
        :y="yScale(barDataEntry.count)"
        :width="xScale.bandwidth()"
        :height="svgInnerHeight - yScale(barDataEntry.count)"
      ></rect>

      <g v-yaxis="{ scale: yScale }" />

      <g :transform="`translate(0, ${svgInnerHeight})`">
        <g v-xaxis="{ scale: xScale, ticks: numberOfXTicks }" />
        <range-slider
          :startX="xScale(selectedRangeStart)"
          :endX="xScale(selectedRangeEnd)"
        ></range-slider>
      </g>
    </g>
  </svg>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { scaleLinear, scaleBand } from "d3-scale";
import { max } from "d3-array";
import { PreparedHistogramDataEntry } from "../interfaces";
import { axisBottom, axisLeft, ScaleBand, select } from "d3";
import { DateTime } from "luxon";
import RangeSlider from "./RangeSlider.vue";
import { Interval } from "luxon";

export default defineComponent({
  name: "BarChart",
  components: { RangeSlider },
  props: {
    barData: {
      // Data must be sorted before being passed to the chart
      required: true,
      type: Object as () => PreparedHistogramDataEntry[],
    },
    numberOfXTicks: {
      type: Number,
      default: 15,
    },
  },
  data: function () {
    return {
      svgStyle: {
        margin: {
          top: 10,
          right: 30,
          bottom: 30,
          left: 40,
        },
        width: 1296,
        height: 220,
      },
      selectedRangeStart: "1981-2",
      selectedRangeEnd: "2013-7",

      numberOfMonths: 60,
    };
  },
  directives: {
    yaxis: {
      beforeUpdate(el, binding): void {
        const scaleFunction = binding.value.scale;
        const d3Axis = axisLeft<number>(scaleFunction).ticks(5);
        d3Axis(select(el as unknown as SVGGElement));
      },
    },
    xaxis: {
      beforeUpdate(el, binding): void {
        const scaleFunction = binding.value.scale;
        const numberOfTicks = binding.value.ticks;
        const numberofElems = scaleFunction.domain().length;
        const moduloVal = Math.floor(numberofElems / numberOfTicks);

        const d3Axis = axisBottom<number>(scaleFunction).tickValues(
          scaleFunction.domain().filter(function (d: string, i: number) {
            return !(i % moduloVal);
          })
        );
        d3Axis(select(el as unknown as SVGGElement)); // TODO: TS: There's probably a better solution than this double casting
      },
    },
  },

  computed: {
    selectedRangeStartIndex(): number {
      return this.truncatedBarData.findIndex((e) => {
        return e.yearMonth === this.selectedRangeStart;
      });
    },
    selectedRangeEndIndex(): number {
      return this.truncatedBarData.findIndex((e) => {
        return e.yearMonth === this.selectedRangeEnd;
      });
    },
    dataMax(): number {
      const maxVal = max(
        this.truncatedBarData,
        (d: PreparedHistogramDataEntry) => {
          return d.count;
        }
      );
      return maxVal ? maxVal : 0;
    },
    truncatedBarData(): PreparedHistogramDataEntry[] {
      return this.barData.filter((e) =>
        this.xScaleDomain.includes(e.yearMonth)
      );
    },
    xScaleDomain(): string[] {
      function* months(interval: Interval) {
        let cursor = interval.start.startOf("month");
        while (cursor < interval.end) {
          yield cursor;
          cursor = cursor.plus({ months: 1 });
        }
      }

      const endDate = DateTime.now();
      const startDate = endDate.minus({ month: this.numberOfMonths });
      const interval = Interval.fromDateTimes(startDate, endDate);

      return Array.from(months(interval)).map(
        (m: DateTime) => m.year + "-" + m.month
      );
    },
    xScale(): ScaleBand<string> {
      return scaleBand()
        .range([0, this.svgInnerWidth])
        .paddingInner(0.3)
        .domain(this.xScaleDomain);
    },
    yScale() {
      return scaleLinear()
        .rangeRound([this.svgInnerHeight, 0])
        .domain([0, this.dataMax]);
    },
    svgInnerWidth: function (): number {
      return (
        this.svgStyle.width -
        this.svgStyle.margin.left -
        this.svgStyle.margin.right
      );
    },
    svgInnerHeight: function (): number {
      return (
        this.svgStyle.height -
        this.svgStyle.margin.top -
        this.svgStyle.margin.bottom
      );
    },
  },
});
</script>

<style scoped>
.riparias-bar {
  fill: #00a58d;
  opacity: 0.3;
}

.selected {
  fill: red !important;
}

.riparias-bar:hover {
  opacity: 1;
}
</style>
