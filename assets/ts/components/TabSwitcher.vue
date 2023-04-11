<template>
  <ul class="nav nav-tabs">
    <li v-for="tab in props.tabs" class="nav-item">
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

<script setup lang="ts">
import {Tab} from "@/assets/ts/interfaces";
import {kebabCase} from "lodash";

interface Props {
  modelValue: string;
  tabs: Tab[];
}

const props = defineProps<Props>();

const generateTabId = (tabName: string): string => {
  return `tab-${kebabCase(tabName)}`;
};

</script>
