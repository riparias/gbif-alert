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

<script setup lang="ts">
import {computed} from "vue";

interface Props {
  alertType?: string // "primary" | "secondary" | "success" | "danger" | "warning" | "info" | "light" | "dark"
  dissmissible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  alertType: "primary",
  dissmissible: true,
});

const emit = defineEmits(["clickClose"]);

const alertClasses = computed(() => {
  const styleClass = `alert-${props.alertType}`;
  return { [styleClass]: true, "alert-dismissible": props.dissmissible };
});


</script>
