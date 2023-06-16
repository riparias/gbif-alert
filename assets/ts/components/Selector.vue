<template>
  <div class="row align-items-center mb-3">
    <div class="col">
      <div class="small input-group">
        <input class="form-control form-control-sm" type="text" :placeholder="$t('message.typeHereToFilter')"
               aria-label="search form" v-model="textFilter">
        <button class="btn btn-outline-secondary btn-sm" type="button" id="button-addon2" v-if="textFilter !== ''"
                @click="textFilter=''"><i class="bi bi-x-circle-fill"></i></button>
      </div>
    </div>

    <div v-if="tagsEnabled" class="col small">
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

  <p class="small">{{ $t('message.selectedEntries') }} {{ numSelectedEntries }}/{{ numAvailableEntries }}</p>

  <table v-if="linesForDisplay.length > 0" class="table table-hover table-sm">
    <thead>
    <tr>
      <th scope="col"><input
          class="form-check-input"
          type="checkbox"
          v-model="allVisibleLinesSelected"
      />
      </th>

      <th v-for="columnConfig in props.columnsConfig" scope="col"
          :class="{'text-primary': sortBy === columnConfig.dataIndex}" @click="changeSort(columnConfig.dataIndex)">
        {{ columnConfig.label }}
        <i v-if="sortBy === columnConfig.dataIndex"
           :class="sortDirection === 'asc' ? 'bi bi-caret-up-fill' : 'bi bi-caret-down-fill'"></i>
      </th>

      <th v-if="tagsEnabled" scope="col">
        {{ $t("message.tags") }}
      </th>
    </tr>
    </thead>

    <tbody>
    <tr v-for="line in linesForDisplay" :key="line.id">
      <td>
        <input
            class="form-check-input"
            type="checkbox"
            :value="line.id"
            v-model="selectedEntriesIds"
        />
      </td>
      <td v-for="columnConfig in props.columnsConfig">
        <span v-if="!columnConfig.formatter"
              v-html="highlightText(line.columnData[columnConfig.dataIndex].toString(), textFilter)"></span>
        <span v-else
              v-html="columnConfig.formatter(highlightText(line.columnData[columnConfig.dataIndex].toString(), textFilter))"></span>
      </td>

      <td v-if="tagsEnabled">
            <span v-for="tag in line.tags"
                  :style="getStyleForTag(tag)"
                  class="badge bg-secondary mx-1">
              {{ tag }}
            </span>
      </td>
    </tr>
    </tbody>
  </table>

  <p v-else class="small">{{ $t("message.noMatchingResultsFound") }}</p>
</template>

<script setup lang="ts">
import {ColumnMetadata, DataRow} from "../interfaces";
import {computed, ref} from "vue";
import {legibleColor, wordToColor} from "../helpers";

const textFilter = ref<string>('');
const tagsFilter = ref<string[]>([]);
const sortBy = ref<number>(0);  // index of the field (in the DataRow columnData array) to sort by
const sortDirection = ref<'asc' | 'desc'>('asc');

interface Props {
  columnsConfig: ColumnMetadata[]
  availableEntries: DataRow[]
  modelValue: number[]
}

const props = withDefaults(defineProps<Props>(), {
  availableEntries: () => [],
  modelValue: () => []
});

const selectedEntriesIds = computed({
  get() {
    return props.modelValue;
  },
  set(newVal) {
    emit('update:modelValue', newVal)
  }
});

const numSelectedEntries = computed(function () {
  return selectedEntriesIds.value.length;
})

const numAvailableEntries = computed(function () {
  return props.availableEntries.length;
})

const availableTags = computed(() => {
  // All available tags
  const tags = new Set<string>();

  props.availableEntries.forEach((e) => {
    if (e.tags) {
      e.tags.forEach((t) => tags.add(t));
    }
  });
  return Array.from(tags).sort();
});

const tagsEnabled = computed(() => {
  // True if there are tags to filter by
  return availableTags.value.length > 0;
});

const allVisibleLinesSelected = computed({
  get: (): boolean => {
    // True if all visible lines are selected
    return linesForDisplay.value.every((line) => selectedEntriesIds.value.includes(line.id));
  },
  set: (value: boolean) => {
    // Select or deselect all visible lines
    if (value) {
      selectedEntriesIds.value = linesForDisplay.value.map((line) => line.id);
    } else {
      selectedEntriesIds.value = [];
    }
  }
});

const linesForDisplay = computed((): DataRow[] => {
  // All visible lines, sorted and filtered => ready to be displayed
  let lines = props.availableEntries.slice();

  // Filtering by text
  lines = lines.filter((row) => {
    return row.columnData.some((value) => {
      if (typeof value === 'string') {
        return value.toLowerCase().includes(textFilter.value.toLowerCase());
      } else if (typeof value === 'number') {
        return value.toString().includes(textFilter.value);
      } else {
        return false;
      }
    });
  });

  // Filtering by tags
  if (tagsFilter.value.length > 0) {
    lines = lines.filter((l) => {
      return tagsFilter.value.every((tag) => l.tags && l.tags.includes(tag));
    });
  }

  lines = lines.sort((a, b) => {
    const val_a = a.columnData[sortBy.value];
    const val_b = b.columnData[sortBy.value];

    if (typeof val_a === 'string' && typeof val_b === 'string') {
      return val_a.localeCompare(val_b);
    } else if (typeof val_a === 'number' && typeof val_b === 'number') {
      return val_a - val_b;
    } else {
      return 0;
    }
  });

  if (sortDirection.value === 'desc') {
    lines = lines.reverse();
  }

  return lines;
});

const changeSort = (dataIndex: number) => {
  // Change the sort column
  if (dataIndex === sortBy.value) {
    // Same column, change direction
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  } else {
    // New column, sort ascending
    sortBy.value = dataIndex;
    sortDirection.value = 'asc';
  }
}

const getStyleForTag = (tag: string) => {
  return {
    backgroundColor: wordToColor(tag) + '!important',
    color: legibleColor(wordToColor(tag)) + '!important'
  }
}

const highlightText = (text: string, substring: string): string => {
  // Highlight a substring in a text, returns an HTML string
  const index = text.toLowerCase().indexOf(substring.toLowerCase());
  if (index === -1) {
    return text;
  }

  return text.substring(0, index) + '<span style="background: yellow">' + text.substring(index, index + substring.length) + '</span>' + text.substring(index + substring.length);
}

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