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
        v-for="barDataEntry in barData"
        :key="barDataEntry.yearMonth"
        :x="xScale(barDataEntry.yearMonth)"
        :y="yScale(barDataEntry.count)"
        :width="xScale.bandwidth()"
        :height="svgInnerHeight - yScale(barDataEntry.count)"
      ></rect>

      <g v-yaxis="{ scale: yScale }" />

      <g :transform="`translate(0, ${svgInnerHeight})`">
        <g v-xaxis="{ scale: xScale, ticks: numberOfXTicks }" />
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

export default defineComponent({
  name: "BarChart",
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
    dataMax(): number {
      const maxVal = max(this.barData, (d: PreparedHistogramDataEntry) => {
        return d.count;
      });
      return maxVal ? maxVal : 0;
    },
    xScale(): ScaleBand<string> {
      return scaleBand()
        .range([0, this.svgInnerWidth])
        .paddingInner(0.3)
        .domain(
          this.barData.map((d) => {
            return d.yearMonth;
          })
        );
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
  opacity: 0.6;
}

.riparias-bar:hover {
  opacity: 1;
}
</style>
