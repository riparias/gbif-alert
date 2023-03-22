<template>
  <div class="pterois-species-selector">
    <p v-for="species in props.availableSpecies">
      <input
          class="form-check-input"
          type="checkbox"

          :value="species.id"
          :id="'pterois-species-selector-entry-' + species.id"
          v-model="selectedSpeciesIds"
      />
      <label
          class="form-check-label"
          :for="'pterois-species-selector-entry-' + species.id"
      >
        <span class="fst-italic"> {{ species.scientificName }}</span> ({{ species.vernacularName }})
      </label>
    </p>

  </div>
</template>

<script setup lang="ts">
import {SpeciesInformation} from "@/assets/ts/interfaces";
import {ref, watch} from "vue";

const props = defineProps<{
  availableSpecies: SpeciesInformation[]
}>()

const selectedSpeciesIds = ref<number[]>([]);

const emit = defineEmits(['update:modelValue']);

watch(selectedSpeciesIds, (newVal) => {
  emit('update:modelValue', newVal)
})
</script>

