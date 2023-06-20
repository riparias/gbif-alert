<template>
  <div class="alert" :class="alertClasses" role="alert">
    <slot></slot>
    <button v-if="dismissible"
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
  dismissible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  alertType: "primary",
  dismissible: true,
});

const emit = defineEmits(["clickClose"]);

const alertClasses = computed(() => {
  const styleClass = `alert-${props.alertType}`;
  return { [styleClass]: true, "alert-dismissible": props.dismissible };
});
</script>
