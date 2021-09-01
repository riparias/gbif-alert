<template>
  <p>{{ reversedGreeting }} Vue! (from Typescript single file component)</p>
</template>

<script lang="ts">
import Vue from 'vue';

const Component = Vue.extend({
  data: function () {
    return {
      greeting: "Hello"
    };
  },
  computed: {
    reversedGreeting: function (): string {
      return this.greeting.split("").reverse().join("");
    }
  }
});

export default Component;
</script>

<style scoped>
p {
  font-size: 2em;
  text-align: center;
}
</style>