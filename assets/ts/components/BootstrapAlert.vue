<template>
  <div class="alert" :class="alertClasses" role="alert">
    <slot></slot>
    <button
      type="button"
      class="btn-close"
      aria-label="Close"
      @click="$emit('clickClose')"
    ></button>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "BootstrapAlert",
  props: {
    alertType: {
      type: String, // "primary" | "secondary" | "success" | "danger" | "warning" | "info" | "light" | "dark"
      default: "primary",
    },
    dissmissible: {
      type: Boolean,
      default: true,
    },
  },
  emits: ["clickClose"],
  computed: {
    alertClasses: function (): Object {
      const styleClass = `alert-${this.alertType}`;
      return { [styleClass]: true, "alert-dismissible": this.dissmissible };
    },
  },
});
</script>
