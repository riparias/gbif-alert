<template>
  <div class="pterois-species-selector">
    <div class="small mb-3 input-group">
      <input class="form-control form-control-sm" type="text" placeholder="type here to filter species..." aria-label="search form" v-model="search">
      <button class="btn btn-outline-secondary btn-sm" type="button" id="button-addon2" v-if="search != ''" @click="search=''"><i class="bi bi-x-circle-fill"></i></button>
    </div>

    <table v-if="lines.length > 0" class="table table-hover table-sm">
      <thead>
        <tr>
          <th scope="col"><input
                class="form-check-input"
                type="checkbox"
                v-model="allVisibleLinesSelected"
            />
          </th>

          <th scope="col" :class="{'text-primary': sortBy === 'scientific'}" @click="sortBy = 'scientific'">
            Scientific name
          </th>

          <th scope="col" :class="{'text-primary': sortBy === 'vernacular' }" @click="sortBy = 'vernacular'">
            Vernacular name
          </th>

          <th scope="col" :class="{'text-primary': sortBy === 'gbifKey' }" @click="sortBy = 'gbifKey'">
            GBIF taxon key
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="line in lines" :key="line.id">
          <td>
            <input
                class="form-check-input"
                type="checkbox"
                :value="line.id"
                v-model="selectedSpeciesIds"
            />
          </td>
          <td><i>{{ line.scientificName }}</i></td>
          <td>{{ line.vernacularName }}</td>
          <td>{{ line.gbifTaxonKey }}</td>
        </tr>
      </tbody>
    </table>

    <p v-else class="small">No matching species found.</p>

  </div>
</template>

<script setup lang="ts">
import {SpeciesInformation} from "@/assets/ts/interfaces";
import {computed, ref, watch} from "vue";

// Props
const props = defineProps<{
  availableSpecies: SpeciesInformation[]
  modelValue: number[] // Array of selected species IDs
}>()

// Reactive data
const selectedSpeciesIds = ref<number[]>(props.modelValue);
const sortBy = ref<string>('scientific');
const search = ref<string>('');

// Computed data
const lines = computed(() => {
  // All visible lines, sorted and filtered
  let species = props.availableSpecies.slice();

  species = species.filter((s) => {
    const scientificNameMatches = s.scientificName.toLowerCase().includes(search.value.toLowerCase());
    const vernacularNameMatches = s.vernacularName.toLowerCase().includes(search.value.toLowerCase());
    const gbifKeyMatches = s.gbifTaxonKey.toString().includes(search.value);

    return scientificNameMatches || vernacularNameMatches || gbifKeyMatches;
  });

  species = species.sort((a, b) => {
    if (sortBy.value === 'scientific') {
      return a.scientificName.localeCompare(b.scientificName);
    } else if (sortBy.value === 'vernacular') {
      return a.vernacularName.localeCompare(b.vernacularName);
    } else {
      return a.gbifTaxonKey - b.gbifTaxonKey;
    }
  });

  return species;
});

const allVisibleLinesSelected = computed({
  get: () => {
    // True if all visible lines are selected
    return lines.value.every((line) => selectedSpeciesIds.value.includes(line.id));
  },
  set: (value) => {
    // Select or deselect all visible lines
    if (value) {
      selectedSpeciesIds.value = lines.value.map((line) => line.id);
    } else {
      selectedSpeciesIds.value = [];
    }
  }
});


// Various
const emit = defineEmits(['update:modelValue']);
watch(selectedSpeciesIds, (newVal) => {
  emit('update:modelValue', newVal)
})
</script>