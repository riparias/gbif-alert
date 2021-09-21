<template>
  <div>
    <label for="speciesSelector" class="form-label">Species</label>
    <select
      id="speciesSelector"
      v-model="selectedSpecies"
      class="form-select form-select-sm"
      aria-label="Default select example"
    >
      <option :value="null">--- all ---</option>
      <option v-for="s in species" :value="s.id">{{ s.scientificName }}</option>
    </select>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { SpeciesInformation } from "../interfaces";

declare interface SpeciesSelectorData {
  selectedSpecies: Number | null;
}

export default defineComponent({
  name: "SpeciesSelector",
  props: {
    species: {
      type: Array as () => SpeciesInformation[],
      default: [],
    },
  },
  data: function (): SpeciesSelectorData {
    return {
      selectedSpecies: null,
    };
  },
  watch: {
    selectedSpecies(newVal, oldVal) {
      this.$emit("species-changed", this.selectedSpecies);
    },
  },
});
</script>
