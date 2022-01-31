<template>
  <div
    :style="{
      'margin-left': leftMargin + 'px',
      'margin-right': rightMargin + 'px',
    }"
  >
    <div id="slider-round" ref="slider-root" class="slider-styled"></div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import noUiSlider, { API } from "nouislider";
import "nouislider/dist/nouislider.css";

interface NewRangeSliderData {
  slider: API | null;
}

export default defineComponent({
  name: "NewRangeSlider",
  props: {
    numberOfMonths: {
      required: true,
      type: Number,
    },
    initialValues: {
      required: true,
      type: Object as () => number[],
    },
    leftMargin: {
      type: Number,
      default: 0,
    },
    rightMargin: {
      type: Number,
      default: 0,
    },
  },
  emits: ["updateValue"],
  data: function (): NewRangeSliderData {
    return {
      slider: null,
    };
  },
  mounted() {
    this.slider = noUiSlider.create(this.$refs["slider-root"] as HTMLElement, {
      start: this.initialValues,
      connect: true,
      step: 1,
      range: {
        min: 0,
        max: this.numberOfMonths - 1,
      },
    });

    this.slider.on("update", (values) => {
      this.$emit(
        "updateValue",
        values.map((v: any) => parseInt(v))
      );
    });
  },
});
</script>

<style>
#slider-round {
  height: 10px;
}

#slider-round .noUi-connect {
  background: red;
  opacity: 0.3;
}

#slider-round .noUi-handle {
  height: 18px;
  width: 18px;
  top: -5px;
  right: -9px; /* half the width */
  border-radius: 9px;
}
</style>
