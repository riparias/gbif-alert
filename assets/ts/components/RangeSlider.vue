<template>
  <div
    :style="{
      'padding-left': leftMargin + 'px',
      'padding-right': rightMargin + 'px',
      width: 1116 + 'px',
    }"
    class="mx-auto"
  >
    <div id="slider-round" ref="slider-root" class="slider-styled"></div>
  </div>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import noUiSlider, {API} from "nouislider";
import "nouislider/dist/nouislider.css";

interface RangeSliderData {
  slider: API | null;
}

export default defineComponent({
  name: "RangeSlider",
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
    sliderDisabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["updateValue"],
  data: function (): RangeSliderData {
    return {
      slider: null,
    };
  },
  methods: {
    updateDisabledAttribute: function () {
      if (this.slider !== null) {
        if (this.sliderDisabled === true) {
          this.slider.target.setAttribute("disabled", "true");
        } else {
          this.slider.target.removeAttribute("disabled");
        }
      }
    },
  },
  watch: {
    sliderDisabled: {
      immediate: true,
      handler: function () {
        this.updateDisabledAttribute();
      },
    },
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

    this.updateDisabledAttribute();
  },
});
</script>

<style>
#slider-round {
  height: 10px;
}

#slider-round .noUi-connect {
  background: #198754;
  opacity: 1;
}

#slider-round[disabled] .noUi-connect {
  background: #bababa;
}

#slider-round .noUi-handle {
  height: 18px;
  width: 18px;
  top: -5px;
  right: -9px; /* half the width */
  border-radius: 9px;
}
</style>
