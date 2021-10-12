<template>
  <ul class="nav nav-tabs">
    <li v-for="tabName in tabNames" class="nav-item">
      <a
        class="nav-link"
        :class="{
          active: tabName === modelValue,
          'bg-light': tabName === modelValue,
        }"
        href="#"
        @click="$emit('update:modelValue', tabName)"
        >{{ tabName }}
      </a>
    </li>
  </ul>
</template>

<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "TabSwitcher",
  props: {
    modelValue: String,
    tabNames: Array,
  },
});
</script>
