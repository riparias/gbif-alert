<template>
  <circle :cx="startX" :cy="y" r="5" :fill="color" />
  <circle :cx="endX" :cy="y" r="5" :fill="color" />
  <line :x1="startX" :y1="y" :x2="endX" :y2="y" :stroke="color" />
</template>

<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "RangeSlider",
  props: {
    y: {
      type: Number,
      default: 25,
    },
    startX: {
      type: Number,
      required: true,
    },
    endX: {
      type: Number,
      required: true,
    },
    color: {
      type: String,
      default: "red",
    },
  },
});
</script>
