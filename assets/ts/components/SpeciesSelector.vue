<template>
  <div class="pterois-species-selector">
    <div class="row align-items-center mb-3">
      <div class="col">
        <div class="small input-group">
          <input class="form-control form-control-sm" type="text" :placeholder="$t('message.filterByNameOrTaxonKey')" aria-label="search form" v-model="textFilter">
          <button class="btn btn-outline-secondary btn-sm" type="button" id="button-addon2" v-if="textFilter !== ''" @click="textFilter=''"><i class="bi bi-x-circle-fill"></i></button>
        </div>
      </div>

      <div class="col small">
        {{ $t("message.filterByTags") }}
        <span v-for="tag in availableTags"
              :style="getStyleForTag(tag)"
              :class="tagsFilter.includes(tag) ? 'tag-filter-enabled' : 'tag-filter-disabled'"
              class="badge bg-secondary mx-1"
              @click="tagsFilter.includes(tag) ? tagsFilter = tagsFilter.filter((t) => t !== tag) : tagsFilter.push(tag)"
        >
          {{ tag }}
          </span>
      </div>
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
            {{ $t("message.scientificName") }}
          </th>

          <th scope="col" :class="{'text-primary': sortBy === 'vernacular' }" @click="sortBy = 'vernacular'">
            {{ $t("message.vernacularName") }}
          </th>

          <th scope="col" :class="{'text-primary': sortBy === 'gbifKey' }" @click="sortBy = 'gbifKey'">
            {{ $t("message.gbifTaxonKey") }}
          </th>

          <th scope="col">
            {{ $t("message.tags") }}
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
          <td><i v-html="highlightText(line.scientificName, textFilter)"></i></td>
          <td v-html="highlightText(line.vernacularName, textFilter)"></td>
          <td>
              <a :href="'https://www.gbif.org/species/' + line.gbifTaxonKey.toString()" target="_blank">
                  <span v-html="highlightText(line.gbifTaxonKey.toString(), textFilter)"></span>
              </a>
          </td>
          <td>
            <span v-for="tag in line.tags"
                  :style="getStyleForTag(tag)"
                  class="badge bg-secondary mx-1">
              {{ tag }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-else class="small">{{ $t("message.noMatchingSpeciesFound") }}</p>

  </div>
</template>

<script setup lang="ts">
import {SpeciesInformation} from "../interfaces";
import {computed, ref, watch} from "vue";
import {legibleColor, wordToColor} from "../helpers";

// Props
const props = defineProps<{
  availableSpecies: SpeciesInformation[]
  modelValue: number[] // Array of selected species IDs
}>()

// Reactive data
const selectedSpeciesIds = computed({
  get () {
    return props.modelValue;
  },

  set (value) {
    return emit('update:modelValue', value)
  }
});

const sortBy = ref<string>('scientific');
const textFilter = ref<string>('');
const tagsFilter = ref<string[]>([]);

// Computed data
const lines = computed(() => {
  // All visible lines, sorted and filtered
  let species = props.availableSpecies.slice();

  // Filtering by text
  species = species.filter((s) => {
    const scientificNameMatches = s.scientificName.toLowerCase().includes(textFilter.value.toLowerCase());
    const vernacularNameMatches = s.vernacularName.toLowerCase().includes(textFilter.value.toLowerCase());
    const gbifKeyMatches = s.gbifTaxonKey.toString().includes(textFilter.value);

    return scientificNameMatches || vernacularNameMatches || gbifKeyMatches;
  });

  // Filtering by tag
  if (tagsFilter.value.length > 0) {
    species = species.filter((s) => {
      return tagsFilter.value.every((tag) => s.tags.includes(tag));
    });
  }

  // Sorting
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

const availableTags = computed(() => {
  // All available tags
  const tags = new Set<string>();
  props.availableSpecies.forEach((s) => {
    s.tags.forEach((t) => tags.add(t));
  });
  return Array.from(tags).sort();
});

// Methods
const getStyleForTag = (tag: string) => {
  return {
    backgroundColor: wordToColor(tag) + '!important',
    color: legibleColor(wordToColor(tag)) + '!important'
  }
}

const highlightText = (text: string, substring: string) => {
  // Highlight a substring in a text, returns an HTML string
  const index = text.toLowerCase().indexOf(substring.toLowerCase());
  if (index === -1) {
    return text;
  }

  return text.substring(0, index) + '<span style="background: yellow">' + text.substring(index, index + substring.length) + '</span>' + text.substring(index + substring.length);
}

// Various
const emit = defineEmits(['update:modelValue']);
</script>

<style>
/* Unfortunately we cannot scope the style due to https://github.com/vuejs/vue-loader/issues/1915 */
.tag-filter-enabled {
  opacity: 1;
}
.tag-filter-disabled {
  opacity: 0.4;
}
</style>