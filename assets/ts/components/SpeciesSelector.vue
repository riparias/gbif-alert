<template>
  <select v-model="selectedSpecies" class="form-select" aria-label="Default select example">
    <option :value="null">--- all ---</option>
    <option v-for="s in species" :value="s.id">{{ s.scientificName }}</option>
  </select>
</template>

<script lang="ts">
import Vue from "vue";
import {SpeciesInformation} from "../interfaces";

declare interface SpeciesSelectorData {
  selectedSpecies: Number | null
}

export default Vue.extend({
  name: "SpeciesSelector",
  props: {
    species: {
      type: Array as () => SpeciesInformation[],
      default: []
    }
  },
  data: function (): SpeciesSelectorData {
    return {
      selectedSpecies: null
    };
  },
  watch: {
    selectedSpecies(newVal, oldVal) {
      this.$emit('species-changed', this.selectedSpecies)
    }
  }
})
</script>

