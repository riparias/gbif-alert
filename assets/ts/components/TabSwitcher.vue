<template>
  <ul class="nav nav-tabs">
    <li v-for="tab in tabs" class="nav-item">
      <a
        :id="generateTabId(tab.id)"
        class="nav-link"
        :class="{
          active: tab.id === modelValue,
          'bg-light': tab.id === modelValue,
        }"
        :href="void 0"
        role="button"
        @click="$emit('update:modelValue', tab.id)"
        >{{ tab.name }}
      </a>
    </li>
  </ul>
</template>

<script lang="ts">
import {defineComponent} from "vue";
import {kebabCase} from "lodash";

export default defineComponent({
  name: "TabSwitcher",
  props: {
    modelValue: String,
    tabs: Array,
  },
  methods: {
    generateTabId(tabName: string): string {
      return `tab-${kebabCase(tabName)}`;
    },
  },
});
</script>
