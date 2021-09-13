<template>
  <ul class="nav nav-pills">
    <li v-for="tabName in tabNames" class="nav-item">
      <a
        class="nav-link"
        :class="{ active: tabName == value }"
        href="#"
        @click="$emit('input', tabName)"
        >{{ tabName }}
      </a>
    </li>
  </ul>
</template>

<script lang="ts">
import Vue from "vue";

export default Vue.extend({
  name: "TabSwitcher",
  props: {
    value: String,
    tabNames: Array,
  },
});
</script>
