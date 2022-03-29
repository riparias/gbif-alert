<template>
  <ul class="nav nav-tabs">
    <li v-for="tabName in tabNames" class="nav-item">
      <a
        :id="generateTabId(tabName)"
        class="nav-link"
        :class="{
          active: tabName === modelValue,
          'bg-light': tabName === modelValue,
        }"
        :href="void 0"
        role="button"
        @click="$emit('update:modelValue', tabName)"
        >{{ tabName }}
      </a>
    </li>
  </ul>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { kebabCase } from "lodash";

export default defineComponent({
  name: "TabSwitcher",
  props: {
    modelValue: String,
    tabNames: Array,
  },
  methods: {
    generateTabId(tabName: string): string {
      return `tab-${kebabCase(tabName)}`;
    },
  },
});
</script>
